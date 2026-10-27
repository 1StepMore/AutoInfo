# Capability verification 27x3: evidence pack

**Is the production side feature-complete and verified? No.** Of the 81 cells,
35 reach the top verified layer (L3), and every one of those 35 is an unkeyed
result: no keyed production path was verified today. The other 46 cells are
honest blocks. The 36 gated cells were never invoked because the LLM
prerequisite is absent; 3 `report:video` cells cannot render because this host
has no Chrome; 7 ai-commercial digest cells are refused by the digest freshness
gate over stale KB entries that processing cannot refresh without a key. The
structural check (L2) and the artifact check (L3) passed in all 35 rows where an
artifact was produced. L1 semantic judging could not run for the new artifacts
because it also needs an LLM key, so no L1 result in this pack is a capability
verification. The run is `keyed=0, unkeyed=81`, and there are 0 unexplained
failures.

## Capability matrix

Every row below is an unkeyed result. The 36 rows marked `Gated=yes` were never
invoked. Details are trimmed to about 120 characters; the untrimmed text stays in
`matrix.md`, and every verdict is regenerated from `matrix.json`.

Counts: rows=81 · L3=35 · blocked-no-llm-key=36 · blocked-no-browser=3 · blocked-stale-sources=7 · gated=36 · non-gated=45 · keyed=0 · unkeyed=81

| Domain | Cell | Gated | Keyed | Reached | L1 | L2 | L3 | Duration (s) | Detail |
|---|---|---|---|---|---|---|---|---|---|
| ai-commercial | column:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| ai-commercial | digest:agent | no | unkeyed | blocked-stale-sources | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-stale-sources |
| ai-commercial | digest:audio | no | unkeyed | blocked-stale-sources | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-stale-sources |
| ai-commercial | digest:audiobook | no | unkeyed | blocked-stale-sources | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-stale-sources |
| ai-commercial | digest:epub | no | unkeyed | blocked-stale-sources | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-stale-sources |
| ai-commercial | digest:html | no | unkeyed | blocked-stale-sources | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-stale-sources |
| ai-commercial | digest:json | no | unkeyed | blocked-stale-sources | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-stale-sources |
| ai-commercial | digest:markdown | no | unkeyed | blocked-stale-sources | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-stale-sources |
| ai-commercial | enterprise-briefing:html | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| ai-commercial | enterprise-briefing:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| ai-commercial | magazine-digest:html | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| ai-commercial | magazine-digest:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| ai-commercial | premium-briefing:html | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| ai-commercial | premium-briefing:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| ai-commercial | presentation:agent | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| ai-commercial | presentation:html | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| ai-commercial | presentation:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| ai-commercial | report:agent | no | unkeyed | L3 | pass | pass | pass | 0.01 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/ai-commercial/report-agent-20261027-094828-490226.... |
| ai-commercial | report:audio | no | unkeyed | L3 | pass | pass | pass | 0.027 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/ai-commercial/report-audio-20261027-094848-945363.... |
| ai-commercial | report:audiobook | no | unkeyed | L3 | pass | pass | pass | 0.03 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/ai-commercial/report-audiobook-20261027-094859-913... |
| ai-commercial | report:epub | no | unkeyed | L3 | pass | pass | pass | 0.011 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/ai-commercial/report-epub-20261027-094904-281749.e... |
| ai-commercial | report:html | no | unkeyed | L3 | pass | pass | pass | 0.013 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/ai-commercial/report-html-20261027-094906-721684.h... |
| ai-commercial | report:json | no | unkeyed | L3 | pass | pass | pass | 0.01 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/ai-commercial/report-json-20261027-094909-291135.j... |
| ai-commercial | report:markdown | no | unkeyed | L3 | pass | pass | pass | 0.014 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/ai-commercial/report-markdown-20261027-094911-9329... |
| ai-commercial | report:video | no | unkeyed | blocked-no-browser | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-browser |
| ai-commercial | tutorial:agent | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| ai-commercial | tutorial:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| language-learning | column:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| language-learning | digest:agent | no | unkeyed | L3 | pass | pass | pass | 0.011 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/digest-agent-20261027-093839-644... |
| language-learning | digest:audio | no | unkeyed | L3 | pass | pass | pass | 0.029 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/digest-audio-20261027-093855-772... |
| language-learning | digest:audiobook | no | unkeyed | L3 | pass | pass | pass | 0.032 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/digest-audiobook-20261027-093947... |
| language-learning | digest:epub | no | unkeyed | L3 | pass | pass | pass | 0.014 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/digest-epub-20261027-093953-0007... |
| language-learning | digest:html | no | unkeyed | L3 | pass | pass | pass | 0.02 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/digest-html-20261027-093957-7524... |
| language-learning | digest:json | no | unkeyed | L3 | pass | pass | pass | 0.013 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/digest-json-20261027-094002-1670... |
| language-learning | digest:markdown | no | unkeyed | L3 | pass | pass | pass | 0.015 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/digest-markdown-20261027-094006-... |
| language-learning | enterprise-briefing:html | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| language-learning | enterprise-briefing:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| language-learning | magazine-digest:html | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| language-learning | magazine-digest:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| language-learning | premium-briefing:html | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| language-learning | premium-briefing:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| language-learning | presentation:agent | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| language-learning | presentation:html | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| language-learning | presentation:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| language-learning | report:agent | no | unkeyed | L3 | pass | pass | pass | 0.011 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/report-agent-20261027-094010-304... |
| language-learning | report:audio | no | unkeyed | L3 | pass | pass | pass | 0.028 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/report-audio-20261027-094028-759... |
| language-learning | report:audiobook | no | unkeyed | L3 | pass | pass | pass | 0.03 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/report-audiobook-20261027-094105... |
| language-learning | report:epub | no | unkeyed | L3 | pass | pass | pass | 0.013 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/report-epub-20261027-094109-2926... |
| language-learning | report:html | no | unkeyed | L3 | pass | pass | pass | 0.016 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/report-html-20261027-094112-7684... |
| language-learning | report:json | no | unkeyed | L3 | pass | pass | pass | 0.01 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/report-json-20261027-094116-2169... |
| language-learning | report:markdown | no | unkeyed | L3 | pass | pass | pass | 0.015 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/language-learning/report-markdown-20261027-094119-... |
| language-learning | report:video | no | unkeyed | blocked-no-browser | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-browser |
| language-learning | tutorial:agent | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| language-learning | tutorial:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| medical-research | column:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| medical-research | digest:agent | no | unkeyed | L3 | pass | pass | pass | 0.05 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/digest-agent-20261027-093224-3536... |
| medical-research | digest:audio | no | unkeyed | L3 | pass | pass | pass | 0.362 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/digest-audio-20261027-093234-8106... |
| medical-research | digest:audiobook | no | unkeyed | L3 | pass | pass | pass | 0.035 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/digest-audiobook-20261027-093319-... |
| medical-research | digest:epub | no | unkeyed | L3 | pass | pass | pass | 0.014 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/digest-epub-20261027-093326-14110... |
| medical-research | digest:html | no | unkeyed | L3 | pass | pass | pass | 0.016 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/digest-html-20261027-093333-34809... |
| medical-research | digest:json | no | unkeyed | L3 | pass | pass | pass | 0.011 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/digest-json-20261027-093339-27632... |
| medical-research | digest:markdown | no | unkeyed | L3 | pass | pass | pass | 0.015 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/digest-markdown-20261027-093345-2... |
| medical-research | enterprise-briefing:html | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| medical-research | enterprise-briefing:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| medical-research | magazine-digest:html | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| medical-research | magazine-digest:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| medical-research | premium-briefing:html | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| medical-research | premium-briefing:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| medical-research | presentation:agent | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| medical-research | presentation:html | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| medical-research | presentation:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| medical-research | report:agent | no | unkeyed | L3 | pass | pass | pass | 0.011 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/report-agent-20261027-093348-3718... |
| medical-research | report:audio | no | unkeyed | L3 | pass | pass | pass | 0.027 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/report-audio-20261027-093402-8191... |
| medical-research | report:audiobook | no | unkeyed | L3 | pass | pass | pass | 0.03 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/report-audiobook-20261027-093440-... |
| medical-research | report:epub | no | unkeyed | L3 | pass | pass | pass | 0.014 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/report-epub-20261027-093443-64168... |
| medical-research | report:html | no | unkeyed | L3 | pass | pass | pass | 0.017 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/report-html-20261027-093446-73368... |
| medical-research | report:json | no | unkeyed | L3 | pass | pass | pass | 0.01 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/report-json-20261027-093449-77644... |
| medical-research | report:markdown | no | unkeyed | L3 | pass | pass | pass | 0.016 | assert_only; artifact=/mnt/d/贯维/AutoInfo/outputs/capability-matrix/medical-research/report-markdown-20261027-093455-0... |
| medical-research | report:video | no | unkeyed | blocked-no-browser | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-browser |
| medical-research | tutorial:agent | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
| medical-research | tutorial:markdown | yes | unkeyed | blocked-no-llm-key | fail | fail | fail | 0.0 | assert_only; no artifact recorded; prior=blocked-no-llm-key |
## Collection and source diagnosis

This run added 143 raw items. The total satisfied source count did not move: the
same 9 sources were already satisfied by earlier collections. The new items are
fresh material for processing, not 9 additional satisfied cells, and they are
recorded here as such.

| Domain | New items | Sources that produced items |
|---|---:|---|
| medical-research | 40 | pubmed 20, arXiv 20 |
| language-learning | 45 | news-in-levels 10, commonlit 15, project-gutenberg 20 |
| ai-commercial | 58 | techcrunch 20, producthunt 20, 36kr 18 |
| **Total** | **143** | |

Source diagnosis over all 78 required `domain x source` pairs:

| Bucket | Count |
|---|---:|
| satisfied | 9 |
| degraded | 5 |
| failing | 3 |
| never-attempted | 59 |
| configured-off | 2 |
| **Total** | **78** |

The unchanged-satisfied note is the honesty check on this section. A larger
collection delta does not raise the satisfied count, and this pack does not
present it as coverage growth. Full row-level detail is in
`source-diagnosis.md` and the captured collector logs under `logs/`.

## KB three-tier status

| Domain | 01-Raw | 02-Draft | 03-Wiki |
|---|---:|---:|---:|
| medical-research | 39 | 0 | 0 |
| language-learning | 26 | 0 | 0 |
| ai-commercial | 5 | 0 | 0 |

Run-start boundary: no Raw row was created during this run, and the newest Raw
row predates it (2026-09-30 09:29:51). The 143 collected items live only in the
gitignored `collections/` caches. No Draft entry and no Wiki entry was created,
because T12 and T13 are blocked on the missing `AUTOINFO_LLM_API_KEY`
(`logs/blockers-2026-10-27.md`).

Success criterion #6 (at least 1 Draft and at least 1 Wiki created during the
run) is **NOT met**. The reason is the blocked key, not a KB defect. No entry
was fabricated to satisfy the criterion.

## Quality gates before and after

L0 (`scripts/quality_gate.py`) before the run, over the historical corpora:

| Domain | Exit | Defects | Files with defects | Class histogram |
|---|---:|---:|---:|---|
| medical-research | 1 | 55 | 52 | H3 46, H2 4, F1 2, C4 2, F2 1 |
| language-learning | 1 | 1 | 1 | H3 1 |
| ai-commercial | 2 | - | - | no rendered `.md` under `outputs/ai-commercial` |

L0 after the run, over `outputs/capability-matrix/<domain>`:

| Domain | Exit | Defects | Files with defects | Class |
|---|---:|---:|---:|---|
| medical-research | 1 | 12 | 12 | H3 bullet serialization glue |
| language-learning | 1 | 2 | 2 | H3 bullet serialization glue |
| ai-commercial | 0 | 0 | 0 | passed |

Two facts must be read together. Structural verification (L2/L3) passes for the artifacts produced in this
run, and L0 still flags 14 Markdown files for the pre-existing H3 bullet
serialization glue class. The flagged files are unkeyed Markdown renders.
The raw count drop from 55 to 12 is **not** a quality improvement: the two runs
measured different corpora: the before run scanned medical-research's 83 pre-existing Markdown files, language-learning's 3 and ai-commercial's 0, while the after run scanned the Markdown files under `outputs/capability-matrix/`.

L1 after the run: **not run**. `scripts/agent_review/battery.py --semantic`
needs an LLM key, and none is configured. The baseline L1 verdict before the run
was 0 PASS / 0 FLAG / 1 ESCALATE
(`logs/l1-baseline-medical-research-2026-10-27.log`).

## Test suite

| Run | Tree | Result | Log |
|---|---|---|---|
| main baseline | `335a7c3f` | 6459 passed, 49 skipped, 0 failed in 1813.79 s | `logs/suite-baseline.txt` |
| PR3 first run | `b7300950` | 6537 passed, 21 failed, 49 skipped in 2381.83 s | `logs/suite-pr3-run1-failed-2026-10-27.log` |
| PR3 final | `b7300950` + T18 | 6557 passed, 1 failed, 49 skipped in 1730.36 s | `logs/suite-pr3.txt` |

The first PR3 run is published because it is the one that found the regressions,
not because it is flattering: 21 digest tests stubbed the private
`_call_llm_for_digest` seam with a two-argument signature, and exposing the
retry budget at the call site added two keyword arguments. The stubs were the
thing that was out of date, and they were widened. One failure remains in the
final run: `test_rss_failure_raises_source_failure` times out against the live
`https://example.com/feed` and asserts the wrong message for the timeout path.
It passes in isolation (13 passed in 5.57 s immediately after) and it belongs to
the registered non-hermetic test class in
`docs/known-limitations/demo-quality-residuals.md` section C, so it is a
pre-existing environment sensitivity, not a PR3 regression. No other test fails
relative to the main baseline.

## Independent verification (T19)

Every acceptance command printed in this pack was re-run from a clean shell on
the PR3 tree. All output is in `logs/anti-fabrication-2026-10-27.log`.

| Check | Command | Result |
|---|---|---|
| 81 rows, per-row layer | `tests/scripts/test_evidence_pack.py` | pass — table rows are re-derived from `matrix.json` |
| Inventory / counts | `python3 scripts/doc_inventory.py --check` | pass |
| (a) `01-Raw` provenance | `python3 scripts/check_kb_provenance.py` | **fails, see below** |
| (b) no fixture sentinel in `outputs/` | `pytest tests/validation/test_no_fixture_artifacts.py` | pass (3 tests) |
| (c) Wiki provenance | `select tier, count(*) ... group by tier` | **vacuous** — 0 Wiki rows |
| Full suite | `pytest -q --timeout=600` | 6557 passed, 49 skipped, 1 failed |

**Check (a) is published as a failure, not a pass.** Of 70 `01-Raw` entries in
the three verification domains, 40 match a `collections/` item exactly, 28 match
only after dropping the query string (the KB copy is the canonical URL, the
cache keeps the source's tracking parameters), and 2 match nothing:
`https://api.openalex.org/works/https://openalex.org/W4409168731` and the same
shape for `W7198700870` — the OpenAlex collector stores the API endpoint with
the work URL appended, so neither string is a resolvable source page. Both
predate this run (this run created **0** KB entries), and neither domain's
capability verdict depends on them, but they are real and are recorded rather
than smoothed over.

**Check (c) is vacuous, not passed.** There are 0 `02-Draft` and 0 `03-Wiki`
entries, so no Wiki entry exists to carry `promotion_source: agent` and no Draft
ancestor exists to point at. That is the same fact that makes success criterion
#6 unmet: this run created 0 KB entries of any tier (the 143 fetched items are
in `collections/`, the KB is untouched).

**Suite.** One failure,
`test_rss_failure_raises_source_failure`, times out against the live
`https://example.com/feed`; it passes in isolation (13 passed in 5.15 s) and is
the registered non-hermetic test class, not a PR3 regression. Everything else
matches or improves on the baseline (6557 vs 6459 passed: +95 new tests minus
the ones that only run under the keyed tree).

## Exact commands

The block below regenerates every table in this file, from the matrix run through
the L0/L1 gates and the source diagnosis.

```bash
# 1. Matrix run, one domain at a time, then the metadata/assert refresh.
.venv/bin/python scripts/capability_matrix.py --domains medical-research --force
.venv/bin/python scripts/capability_matrix.py --domains language-learning
.venv/bin/python scripts/capability_matrix.py --domains ai-commercial --force
.venv/bin/python scripts/capability_matrix.py --domains medical-research,language-learning,ai-commercial --only-assert

# 2. Regenerate the 81-row Markdown table from matrix.json.
.venv/bin/python - <<'PY'
import json
d = json.load(open("docs/dev/validation-reports/capability-27x3/matrix.json"))
rows = d["rows"]
def yn(b): return "pass" if b else "fail"
def trim(s, n=120):
    s = (s or "").replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."
print("Counts: rows=%d · L3=%d · blocked-no-llm-key=%d · blocked-no-browser=%d · blocked-stale-sources=%d · gated=%d · non-gated=%d · keyed=%d · unkeyed=%d"
      % (len(rows), sum(r["reached"]=="L3" for r in rows),
         sum(r["reached"]=="blocked-no-llm-key" for r in rows),
         sum(r["reached"]=="blocked-no-browser" for r in rows),
         sum(r["reached"]=="blocked-stale-sources" for r in rows),
         sum(bool(r["gated"]) for r in rows), sum(not r["gated"] for r in rows),
         sum(r["keyed"]=="keyed" for r in rows), sum(r["keyed"]=="unkeyed" for r in rows)))
print("| Domain | Cell | Gated | Keyed | Reached | L1 | L2 | L3 | Duration (s) | Detail |")
print("|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    print("| %s | %s:%s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
        r["domain"], r["product"], r["format"],
        "yes" if r["gated"] else "no", r["keyed"], r["reached"],
        yn(r["l1"]), yn(r["l2"]), yn(r["l3"]), r["duration_s"], trim(r["detail"])))
PY

# 3. Collection (one attempt per source, --limit 20).
.venv/bin/python -m autoinfo.cli collect --domain medical-research --limit 20
.venv/bin/python -m autoinfo.cli collect --domain language-learning --limit 20
.venv/bin/python -m autoinfo.cli collect --domain ai-commercial --limit 20

# 4. Source diagnosis (78 pairs).
.venv/bin/python scripts/source_diagnosis.py

# 5. L0 before and after.
.venv/bin/python scripts/quality_gate.py outputs/medical-research
.venv/bin/python scripts/quality_gate.py outputs/language-learning
.venv/bin/python scripts/quality_gate.py outputs/ai-commercial
.venv/bin/python scripts/quality_gate.py outputs/capability-matrix/medical-research
.venv/bin/python scripts/quality_gate.py outputs/capability-matrix/language-learning
.venv/bin/python scripts/quality_gate.py outputs/capability-matrix/ai-commercial

# 6. L1 (needs an LLM key; exits ESCALATE without one).
.venv/bin/python scripts/agent_review/battery.py outputs/capability-matrix/medical-research --semantic

# 7. Suite and the evidence-pack consistency test.
.venv/bin/python -m pytest -q --timeout=600
.venv/bin/pytest tests/scripts/test_evidence_pack.py -q
```

## Residual

The 46 non-L3 rows are fully accounted for below: 36 + 3 + 7. The last two rows
are quality residuals rather than cell blocks, and they are listed so the pack
does not hide either one behind the cell counts.

| Class | Rows | Cells | Why it is honest (or not) | Registered |
|---|---:|---|---|---|
| `blocked-no-llm-key` | 36 | the 36 gated cells across the 3 domains | Honest block: the cell was never invoked because the LLM prerequisite is provably absent. It is neither a failure nor a pass. | no |
| `blocked-no-browser` | 3 | `report:video` in each of the 3 domains | Honest block: `RuntimeError: HyperFrames render failed (quality=draft): ... Chrome cannot launch`. This host has no Chrome, only `~/.cache/puppeteer/chrome-headless-shell` remnants. | yes |
| `blocked-stale-sources` | 7 | the 7 ai-commercial digest cells | Honest block: the freshness gate raised `StaleSourceError` because all 5 ai-commercial KB entries are older than the threshold. The 58 freshly collected items cannot refresh the KB without processing, and processing needs the key. Cause chain, not a generation bug. | yes |
| H3 bullet serialization glue in unkeyed Markdown | 14 files | 14 flagged Markdown renders (12 medical-research, 2 language-learning) | Not a block and not a pass: it is a real L0 defect. The artifacts still pass L2/L3 structural checks, so both facts are published together. | yes (section B of the register) |
| Absence of keyed L3 evidence | 81 cells | all 81 cells | Not honest as coverage: it is a gap in evidence, not a product block. The 35 L3 rows prove unkeyed structure only, and no keyed path was exercised. | no |

### New failure classes

This run produced two new classes: `blocked-no-browser` and
`blocked-stale-sources`. Both were added to
`docs/known-limitations/demo-quality-residuals.md` in this same commit. The
register entries name the 3 video cells and the 7 ai-commercial digest cells,
and both entries say plainly that these are unverified cells, not product
defects to be silenced.