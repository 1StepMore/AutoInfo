# Acceptance Run — AutoInfo 1.14.0 (2026-09-29)

Per-dimension verdict table per `docs/dev/acceptance-framework.md` §10 (AC1-AC9).

This report supersedes `docs/archive/acceptance-run-20260816.md` (verdict:
**⚠️ NOT SIGNED OFF**), whose three in-scope blockers B-01/B-02/B-03 are closed
below. B-04 and B-05 are explicitly out of V1 scope and are recorded as such
rather than counted as blockers.

## Evidence basis and its limits

Read this before reading the verdict.

| | |
|---|---|
| Version under test | 1.14.0 at run time. `main` has since advanced to **1.14.1** (`7385c5ad`); the v1.14.0→1.14.1 delta is `_version.py`, the release manifest, `CHANGELOG.md`, two scenario YAMLs and one test fixture — **no `src/autoinfo/**.py` runtime change**, so the evidence below still applies to 1.14.1. |
| Deterministic evidence | `scripts/doc_inventory.py --check` (exit 0), `scripts/coverage_audit.py` |
| Scenario library | 174 scenarios — 86 functional, 88 regression |
| Test suite | 5766 collected |
| MCP surface | 149 tools / 35 categories, 0 phantom tools declared in scenarios |
| Domain coverage | 13/13 demo domains exercised by the scenario library |
| `AUTOINFO_LLM_API_KEY` | set for the targeted LLM run below (BYOK, `${AUTOINFO_LLM_API_KEY}` reference only) |

**LLM evidence (targeted run, 2026-09-30).** A full 174-scenario LLM-enabled
run was attempted and **aborted**: the self-hosted gateway degraded under the
full fan-out (56 `litellm.Timeout` in 2h14m, and 8 occasions where *both*
primary and fallback failed), producing no `manifest.json`. The run was
stopped rather than allowed to spin.

A focused re-run of the five core LLM-gated pipeline scenarios (no
`matrix_domains` fan-out) was then executed against the same gateway:

| Scenario | Verdict | Steps | Wall clock |
|----------|:---:|:---:|---|
| `llm-gated` | **PASS** | 3/3 | 147s |
| `kb-extraction` | **PASS** | 3/3 | 93s |
| `enduser-journey` (B-03 contract) | **PASS** | 2/2 | 145s |
| `cli-llm` | FAIL | 1/2 | 262s |
| `processing` | FAIL | 0/2 | 301s |
| **Total** | **3/5 scenarios** | **9/12 steps** | — |

`AUTOINFO_LLM_API_KEY` resolved on every call — **0 authentication failures**.
The two failures are not authentication or model-quality failures:

- `processing` — both steps fail on `git add` against a `.gitignore`d KB
  path when the scenario runs inside this working copy. Environmental, not LLM.
- `cli-llm` step 1 — 2 × `litellm.Timeout` on the primary model. Step 2 passed.

**What this does and does not establish.** It establishes that the LLM
extraction, KB-promotion, and end-user delivery paths execute end to end
against a live OpenAI-compatible gateway, and it re-confirms the B-03
`content_preference` contract on a live model call. It does **not** establish
the `output-*` families: `output-video` (13 domains), `output-digest-report`
(4), `output-tutorial-presentation` (4), `output-column` (3), `output-ebook`
(2) and `output-simplify-recommend` (2) — 28 domain-expansions in total — were
**not executed**, so the B-01 fix remains verified by scenario *coverage*
(13/13 domains declared and CI-portable), **not** by a completed 13-domain
video render. Sign-off still requires either those families to run against a
gateway that sustains the fan-out, or an explicit director acceptance of
coverage-level proof for B-01.

## Per-dimension verdict table

| Dimension | Verdict | Blockers | Evidence | Notes |
|-----------|:---:|----------|----------|-------|
| AC1 User model integrity | PASS | — | `regression-b1-content-preference` (2 steps, keyless) | B-03 closed: the three-value `content_preference` contract is now exercised end to end — `raw_only`/`processed_only` refuse the conflicting product kind *before* dispatch, `both`/missing/unknown permit both |
| AC2 Data-layer integrity | PASS | — | `pytest tests/kb`; 01-Raw provenance enforcement unchanged | No change this cycle |
| AC3 Dual orientation (agent) | PASS | — | 149 MCP tools / 35 categories; `coverage_audit.py` reports 0 missing scenario tools | — |
| AC3 Dual orientation (human) | PASS | — | 31 CLI command groups; every PR in this cycle was squash-merged by hand | — |
| AC4 Coverage commitment | PASS | — | `required_sources` = 78 across 13 domains; `output-video` `matrix_domains` = 13 | B-01 and B-02 closed — see below |
| AC5 Quality (automated gates) | PASS | — | G0-G7 + D1-D3; G7 (deterministic entity-fact) added this cycle, soft/flag | 7 hard/soft gates; G0/G4 hard |
| AC5 Quality (director review) | **NOT SIGNED — no product-quality finding is established** | #440 / #446 | 227-product machine draft ran to completion (RISK 227 / ESCALATE 0 / PASS 0), but its defect classes were **retracted on 2026-10-02** after the comparison baseline was found to be wrong. What is verified this cycle is the `additional_body` defect (#440) and three reviewer-tool defects; no product defect class survives checking. See the retraction section. |
| AC6 Commercial viability | PARTIAL | — (B-04 out of scope) | Cost dashboard live; Stripe/V2 billing deferred by design | B-04 is V2-deferred per acceptance-framework, not a V1 blocker |
| AC7 Process & governance | PASS | — | Conventional Commits, DCO enforced on every commit, `release-scope` gate active | 3 gates in the release path were found and fixed this cycle (#412, #413) |
| AC8 Documentation health | PASS | — | `doc_inventory.py --check` exit 0; all 7 drift-prone facts match; 0 stray `test_bug_*` | `founder-expectations.md` §14 corrected (#414) — 11 of its rows were disproven by the code |
| AC9 Test & validation health | PASS | — | 5766 tests collected, 0 failures on the non-network subset | 88 regression scenarios guard 81 distinct issues |
| **Overall verdict** | **PENDING DIRECTOR SIGN-OFF** | **0 open V1 blockers** | Targeted LLM run 2026-09-30: 3/5 scenarios, 9/12 steps, 0 auth failures | B-01/B-02/B-03 closed; B-04 V2-deferred; B-05 P3. Core LLM path cleared; `output-*` families (28 domain-expansions) still unexecuted — see Director sign-off |

## AC5 director review — evidence (2026-10-02)

A machine draft over the real product corpus was produced with
`scripts/agent_review/ac5_director_review.py --delivery-dir outputs --semantic`
and reviewed form-by-form. **This is a DRAFT: the module's ceiling is
`RISK`/`ESCALATE` and it can never emit `PASS`**, so it cannot self-certify
AC5 and a human decision is still required.

| | |
|---|---|
| Scope | 227 products, 22 domains, 8 product families, judged on **full** document content |
| Result | **RISK 227 / ESCALATE 0 / PASS 0** |
| Run cost | ~35 min at concurrency 1, **0 timeouts**, 0 auth failures |

### Root cause of the run's own failures

The first attempts produced 5 `ESCALATE` rows and a 14-hour projection. Both
were artifacts of the review tool and of a core LLM defect, not product defects:

- **`additional_body` → `extra_body` (#440).** `llm.py` sent the
  thinking-disable body under an OpenAI SDK name LiteLLM does not recognise, so
  it was dropped silently and reasoning was never disabled. Measured: 45 of 50
  completion tokens on a trivial prompt, `max_tokens` exhausted by thinking
  alone, `content` empty with `finish_reason=length`. A verdict call cost
  **224.4s and returned nothing**; after the fix, **11.0s and 482 chars**. This
  one kwarg also explains 56 `litellm.Timeout` in a single 2h14m validation
  wave and scenarios timing out at their 900s step budget. It disabled nothing
  on any non-DeepSeek gateway, for every judgment gate (G4, G5, `llm_judge`,
  translation QA, scenario judge).
- **Reviewer read window.** The snippet limit (8 000 chars) sat below the real
  product size (max 132 757). The reviewer judged 6-44% of each document and
  reported its own window as a product defect. **All 5 ESCALATE rows were
  false** — those files were complete. The limit is now above the largest real
  product and a file past it ESCALATEs as "cannot judge".

### Defect classes — RETRACTED AND CORRECTED (2026-10-02)

An earlier version of this section reported 65 products with "fabricated or
misattributed content" and 14 with a self-contradicting Executive Summary, and
attributed them to a model that invented entities. **That attribution was
wrong and is withdrawn.** Two of the reported classes do not survive checking
against the source data:

| Originally reported | Verdict on re-check |
|---|---|
| 65 products with fabricated content | **Not fabrication.** `"Jalapeño"` is a real collected entry: `source_platform: techcrunch` (`techcrunch.com/2026/08/25/openais-jalapeno-chip-...`, `collected_at 2026-08-25`) plus a `hackernews` copy. The model's summaries are grounded in real source material. |
| 14 products whose Executive Summary contradicts the body | **One spot-check did not reproduce.** `premium-briefing.md` states "four selected items" and carries exactly four numbered takeaways; the review reported five. The counter was the reviewer's, not the document's. |
| 17 products with empty fields / malformed references | Not re-checked. Unverified. |

**Root cause of the wrong attribution:** the review was compared against
`knowledge/`, a file tree that does not hold the working knowledge base. The
authoritative store is `autoinfo.db` (SQLite; `kb.py` resolves
`db_path = base_path.parent / "autoinfo.db"`, and `output` reads it through
`store.list_entries`). It holds 1821 entries across 23 domains, of which `b2b`
has 149. `knowledge/b2b` contains a single file. Searching the file tree
instead of the database made a well-populated domain look empty, which is what
produced both the false "fabrication" claim and the false "9 domains shipped
72 products from no substantive source" claim.

Re-running the input-adequacy guard against the real database blocks **1 of 23
domains** — `default`, whose only two entries are the literal rows `x` and `y`
with empty summaries and no URL. That block is correct; the 9-domain claim was
not.

### What this section should have said

The only defect classes verified in this cycle are the reviewer-tool defects
recorded above (binary artifacts aborting a run, a non-recursive scan that
turned a real product tree into an empty "all clean" worklist, and a snippet
window below the real product size that produced 5 false ESCALATE rows), plus
the `additional_body` defect in #440. The product-quality classes are **not
established** and need a review run whose comparison baseline is the database.

### The entity-level grounding check: measured, and deliberately not a hard drop

`_ground_synthesis_citations` drops a synthesis sentence **whose citation does
not support it**. A sentence with no citation is untouched by it, by design --
there is no anchor to verify against.

`ungrounded_entities` can flag an ungrounded Title-Case entity, and it is wired
only to the post-render D2 path, which **escalates rather than blocks**.
Promoting it to a synthesis-time drop was measured rather than assumed:

| baseline | fire rate on real Executive Summaries |
|---|---|
| `knowledge/` file tree (wrong baseline) | 93% |
| **`autoinfo.db`** (authoritative) | **32%** (33 of 103 products) |

The first measurement was taken against a near-empty corpus and is withdrawn.
Against the real database the rate is 32%, still far too high to drop output
over: a synthesis legitimately names themes and clusters that no individual
entry title contains ("the strongest cluster", "AI Infrastructure
Consolidation"). The escalate-only decision stands, on a corrected basis.

### The reviewer's own labels are unreliable

Separately from the classification error above, the reviewer's labels do not
survive checking. Of 24 products it labelled "placeholder", **0** contained an
unfilled template section -- it was flagging products that honestly disclosed
placeholder material in their *source* data, which the residual register
(#179/#191) requires be allowed. One product that does carry an unfilled
`### Placeholder Entries` section was not flagged at all. Its counts should be
read as prompts for a human to look, not as measurements.

### A third finding that dissolved on checking — stale artifacts

`self_count_contradictions` fires on 16 products, all `enterprise-briefing.md`,
each claiming "selected N of M key findings" while rendering exactly one Key
Findings entry. Read directly, that is a genuine self-contradiction.

It is not a live defect. `enterprise-briefing.md.j2` today cannot emit that
string: it renders `> **In this briefing**: {{ key_findings|length }} key points
· drawn from {{ references|length }} sources`, and both numbers derive from the
same lists, so they cannot disagree. The string the products carry was emitted
before `86c8e12f` (#385, 2026-09-26); the products were generated 2026-08-26,
a month earlier. All 16 are stale artifacts of the previous template.

Recorded because it is the third finding this cycle that survived a plausible
reading and then dissolved: the "fabrication" class (wrong baseline -- the
`knowledge/` file tree instead of `autoinfo.db`) and the 14 "self-contradiction"
findings (the reviewer's own count was wrong) before this one. The gate itself
is sound and would fire if the invariant broke again; what is wrong is running
it against a corpus the current code cannot have produced.

### `output-*` families — one scenario measured (2026-10-02)

`output-premium-products`, run with the `python` shim on PATH (this box has no
bare `python`, so `kind: cli` steps fail instantly without it) and
`AUTOINFO_LLM_MAX_CONCURRENCY=1`:

| step | result |
|---|---|
| premium-briefing digest (medical-research) | passed, 252s |
| enterprise-briefing report (medical-research) | passed, 180s |
| magazine-digest (general-news) | **failed at the 900s step cap**, no artifact written |

The third step's own command, run standalone in a subprocess exactly as the
scenario runs it, completed in **184s** and wrote 55 367 chars. The step is
correct and the per-step budget is adequate for an isolated call, so the 5x
difference when it runs third in sequence is unexplained.

Two explanations were tested and **both refuted**, recorded so the next person
does not re-run them:

| hypothesis | test | result |
|---|---|---|
| gateway throttling under sustained load | three generations back-to-back on one domain | **refuted** — 269s, 176s, 179s; the third call was *faster* than the first, so there is no cumulative slowdown |
| the scenario runs steps in parallel, and `AUTOINFO_LLM_MAX_CONCURRENCY=1` is a per-process semaphore that parallel subprocesses bypass | `validation.py:2081` and `:2123` | **refuted** — both are `for step in steps:`, i.e. sequential |

What remains untested is whether the harness's per-step timeout accounting
differs from wall-clock (the step reported `None` for an error and exactly
900.014s, which is suspiciously exact), or whether the `kind: cli` subprocess
inherits a different environment from the one I reproduced by hand.

Before #440 every step in this scenario timed out at 900s with the reasoning
budget exhausted. Two of three now pass. That is the measurable effect of the
kwarg fix, and it is the only scenario-family evidence gathered so far.

### Scenario batch, partial results (2026-10-03)

Seven real-LLM `output-*` scenarios launched in sequence with
`AUTOINFO_LLM_MAX_CONCURRENCY=1`. Results so far:

| scenario | result |
|---|---|
| `output-column` | **4 of 6 steps failed** (3025s) |
| `output-discovery` | passed 3/3 (4s) |
| `output-simplify-recommend` | passed 4/4 (1299s) |
| `output-premium-products` (earlier run) | 2 of 3 steps passed |

`output-simplify-recommend` passing 4/4 next to `output-column` failing 4/6 is
the useful contrast: the extra_body fix is not the limiting factor, and
`output-column`'s failures are specific to that scenario rather than systemic.

The batch did not finish. It was still working through
`output-digest-report`, `output-ebook`, `output-tutorial-presentation` and
`output-video` when its log was lost to a `/tmp` cleanup, so those four have no
result at all — not a failure, an absence. Re-run them before relying on this
table.

**Positive evidence for #446/#447:** the synthesis grounding added there fired
7 times in these real runs, each time logging the unsupported terms it dropped
(`Synthesis grounding (#445): dropped a cited sentence whose source does not
support it (unsupported terms: ...)`). That is the mechanism working in the
production path, not only under test.

**A harness defect worth fixing:** the failing steps report
`error: None`. A step that fails without recording why makes every downstream
diagnosis guesswork — it is why the magazine-digest timing gap took two refuted
hypotheses to characterise. A step timeout should report the timeout and the
last observable progress, not `None`.

Remaining five scenarios (`output-simplify-recommend`, `output-digest-report`,
`output-ebook`, `output-tutorial-presentation`, `output-video`) were still
running when this section was written; `output-column` alone consumed 50
minutes, so the batch is slow by construction at concurrency 1.

### What is NOT established

- The fixes are **unverified against fresh output**. The 227 products were
  built by the unfixed code path and have not been regenerated, so this run
  measures what shipped, not what the fixed pipeline produces.
- The `output-*` scenario families still have not been run across all domains
  (B-01 closed the artifact gap; the scenarios were not re-executed).
- This draft does not satisfy AC5 on its own. A human reviewer signs it or does not.

## Blocker disposition

| Blocker | Sev | Status | Evidence |
|---------|-----|--------|----------|
| B-01 — 12 `report×video` cells had no artifact | P1 | **CLOSED** | `output-video` `matrix_domains` extended 2 → 13 (#420). The 13 are exactly the domains `end-user-matrix.yaml` declares. CI-safe: the scenario is LLM-gated, so it reports `unconfigured` rather than rendering. Durability is `validation_delivery.py` copying `collect_artifacts` into `validation-deliveries/<date>/` + `manifest.json` per-cell authenticity. |
| B-02 — 89 source gaps | P1 | **CLOSED** | The figure was never 89 missing collectors: it was `required_sources` compared against collected evidence, and the list had accumulated disabled/GFW-blocked feeds. Corrected to **78** and reconciled against all 13 `sources.yaml`; 3 README domain rows corrected (#416). Medical-research's 7 sources were always configured. |
| B-03 — B1 `content_preference` contract never run | P2 | **CLOSED** | `regression-b1-content-preference` (#420) drives the real `_handle_send_to_enduser` guard over a temp user store, both directions, keyless. |
| B-04 — Stripe / V2 billing | P2 | OUT OF SCOPE | Deferred to V2 by design; not a V1 acceptance blocker. |
| B-05 — 8 failed scenarios (LLM volatility) | P3 | OUT OF SCOPE | Adjudicated non-regression. The 2026-09-30 targeted run re-confirmed the volatility is **gateway-side, not code-side**: 0 auth failures across 12 steps, and the only LLM failure mode observed was `litellm.Timeout` on the primary. A stable-window re-run of all 174 scenarios was attempted and abandoned (see Evidence basis). |

## Findings raised by this cycle, not blockers

- **Three gates in the release path had never been exercised against a release
  PR**: the `pull_request_target` trigger (never fired for a `GITHUB_TOKEN` PR),
  a permanently-`skip`if'd regression test, and the `release-scope` gate
  (rejected the release PR's own required check). Fixed in #412/#413; v1.13.7
  and v1.13.8 have since released unattended.
- **Two documented claims were false and are now corrected**: `§14` claimed
  no Dockerfile, no `--force-full`, no CLI `topics group`, an unused fallback
  chain, and no CSV/GraphML export — all disproven against the code (#414).
- The residual register's "entity factual errors have no deterministic gate"
  was true until G7 landed (#418).

## Director sign-off

This report is evidence-complete but **not self-certified**. Two items require
a human:

1. **AC5 director review** — the quality judgment has not been made.
2. **Overall verdict** — recorded as PENDING, not PASS.

Sign-off requires:

1. **(a) Core LLM path — satisfied 2026-09-30.** The targeted run cleared the
   evidence gap for the extraction / KB / end-user delivery paths
   (`llm-gated` 3/3, `kb-extraction` 3/3, `enduser-journey` 2/2; 0 auth
   failures). The two failing scenarios failed for non-LLM reasons
   (`processing` on a gitignored path; `cli-llm` step 1 on 2 × `Timeout`).
2. **(b) `output-*` families — still open.** 28 domain-expansions across
   `output-video` / `output-digest-report` / `output-tutorial-presentation` /
   `output-column` / `output-ebook` / `output-simplify-recommend` were not
   executed. Either run them against a gateway that sustains the fan-out, or
   record an explicit director acceptance of coverage-level proof for B-01.
3. **(c) A named director signature**, plus the AC5 quality judgment above.

| Field | Value |
|-------|-------|
| Director | _(unsigned)_ |
| Date | _(unsigned)_ |
| Verdict | **PENDING DIRECTOR SIGN-OFF** |
