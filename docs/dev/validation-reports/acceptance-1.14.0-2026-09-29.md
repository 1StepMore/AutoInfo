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
| AC5 Quality (director review) | PENDING | — | — | **Requires a human reviewer.** Not self-certified by this report. |
| AC6 Commercial viability | PARTIAL | — (B-04 out of scope) | Cost dashboard live; Stripe/V2 billing deferred by design | B-04 is V2-deferred per acceptance-framework, not a V1 blocker |
| AC7 Process & governance | PASS | — | Conventional Commits, DCO enforced on every commit, `release-scope` gate active | 3 gates in the release path were found and fixed this cycle (#412, #413) |
| AC8 Documentation health | PASS | — | `doc_inventory.py --check` exit 0; all 7 drift-prone facts match; 0 stray `test_bug_*` | `founder-expectations.md` §14 corrected (#414) — 11 of its rows were disproven by the code |
| AC9 Test & validation health | PASS | — | 5766 tests collected, 0 failures on the non-network subset | 88 regression scenarios guard 81 distinct issues |
| **Overall verdict** | **PENDING DIRECTOR SIGN-OFF** | **0 open V1 blockers** | Targeted LLM run 2026-09-30: 3/5 scenarios, 9/12 steps, 0 auth failures | B-01/B-02/B-03 closed; B-04 V2-deferred; B-05 P3. Core LLM path cleared; `output-*` families (28 domain-expansions) still unexecuted — see Director sign-off |

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
