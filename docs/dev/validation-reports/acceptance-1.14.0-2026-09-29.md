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
| Version under test | 1.14.0 (`src/autoinfo/_version.py`, manifest agrees) |
| Deterministic evidence | `scripts/doc_inventory.py --check` (exit 0), `scripts/coverage_audit.py` |
| Scenario library | 174 scenarios — 86 functional, 88 regression |
| Test suite | 5766 collected |
| MCP surface | 149 tools / 35 categories, 0 phantom tools declared in scenarios |
| Domain coverage | 13/13 demo domains exercised by the scenario library |
| `AUTOINFO_LLM_API_KEY` | **not set in the reporting environment** |

**Limit.** Because no LLM key was available, the LLM-gated scenarios
(`output-video`, `output-digest-report`, G4/G5 judgment paths) were **not
re-executed** in this cycle. Every number above is deterministic evidence.
The B-01 fix below is verified by scenario *coverage* (13/13 domains declared
and CI-portable), **not** by a completed 13-domain video render in this
report. A full LLM-enabled run is required before the verdict is signed.

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
| **Overall verdict** | **PENDING DIRECTOR SIGN-OFF** | **0 open V1 blockers** | — | B-01/B-02/B-03 closed; B-04 V2-deferred; B-05 P3 |

## Blocker disposition

| Blocker | Sev | Status | Evidence |
|---------|-----|--------|----------|
| B-01 — 12 `report×video` cells had no artifact | P1 | **CLOSED** | `output-video` `matrix_domains` extended 2 → 13 (#420). The 13 are exactly the domains `end-user-matrix.yaml` declares. CI-safe: the scenario is LLM-gated, so it reports `unconfigured` rather than rendering. Durability is `validation_delivery.py` copying `collect_artifacts` into `validation-deliveries/<date>/` + `manifest.json` per-cell authenticity. |
| B-02 — 89 source gaps | P1 | **CLOSED** | The figure was never 89 missing collectors: it was `required_sources` compared against collected evidence, and the list had accumulated disabled/GFW-blocked feeds. Corrected to **78** and reconciled against all 13 `sources.yaml`; 3 README domain rows corrected (#416). Medical-research's 7 sources were always configured. |
| B-03 — B1 `content_preference` contract never run | P2 | **CLOSED** | `regression-b1-content-preference` (#420) drives the real `_handle_send_to_enduser` guard over a temp user store, both directions, keyless. |
| B-04 — Stripe / V2 billing | P2 | OUT OF SCOPE | Deferred to V2 by design; not a V1 acceptance blocker. |
| B-05 — 8 failed scenarios (LLM volatility) | P3 | OUT OF SCOPE | Adjudicated non-regression; needs a stable-window LLM re-run. |

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

Sign-off requires: (a) an LLM-enabled scenario run to close the evidence gap
above, and (b) a named director signature.

| Field | Value |
|-------|-------|
| Director | _(unsigned)_ |
| Date | _(unsigned)_ |
| Verdict | **PENDING DIRECTOR SIGN-OFF** |
