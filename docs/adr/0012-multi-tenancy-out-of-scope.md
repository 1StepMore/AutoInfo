<!-- doc-type: adr -->
# 0012. Multi-tenancy isolation is out of scope: AutoInfo stays a single-tenant local agent tool

- **Status**: Accepted
- **Date**: 2026-11-02
- **Author**: Director (owner), recorded by agent
- **Related**: #165 (2026-10-22 review), ADR 0005 (unified envelope), `docs/dev/specs/multi-tenancy-auth.md`, `docs/dev/specs/expectations.md` §3.17 F58

## Context

The 2026-10-22 review on #165 found that multi-tenancy is a **strategic** gap, not a
technical one. Everything *around* tenancy already ships — subscription tiers, per-user
quotas, per-user delivery logs, GDPR export/delete, per-user cost allocation, the
self-service portal — while the isolation boundary alone is absent:

- `docs/dev/specs/multi-tenancy-auth.md` self-describes as *"Never Designed — spec only,
  zero implementation"*.
- `src/autoinfo/config.py:628` — `MultiUserConfig.enabled: bool = False`.
- `actor` is a **caller-declared string** (`src/autoinfo/mcp/server.py:774` —
  `actor = arguments.get("actor") or "agent"`), not an authentication or authorization
  boundary.
- `src/autoinfo/api/server.py:82` binds REST to `127.0.0.1` by default; `:100` sets
  `allow_origins=["*"]`.

That review put one question to the director, and it was explicitly a prerequisite for the
shape of the structural-debt batch #580–#588 (all since closed as `completed`):

> Is AutoInfo's end state a **local agent tool** or a **hosted multi-tenant SaaS**?

On 2026-11-02 the director decided: **multi-tenancy is not being built.**

## Decision

1. **AutoInfo is a single-tenant, locally operated agent tool.** No per-tenant data
   isolation (tenant-scoped keys, per-tenant schemas, row-level tenant filters) will be
   built. No work may be scheduled on the premise that tenancy is coming, and structural
   refactors need not reserve tenant boundaries in module shapes.
2. **The trust boundary is the OS process plus loopback HTTP.** `user_id` (and `actor`) are
   advisory data-scoping cursors for personalization, quota, billing and delivery logs —
   **never** an authorization boundary. No code may treat either as proof of identity.
3. **The REST server's loopback binding is part of the security model, not a convenience.**
   Exposing it on a non-loopback interface without an external authenticating proxy is
   unsupported; `allow_origins=["*"]` makes that unsupported configuration actively unsafe.
4. **`multi-tenancy-auth.md` is design-only reference.** It must not be cited as a planned
   capability. F58 moves from `blocked-with-record` to `out-of-scope` in
   `expectations.md` §3.17. The dispositions of F59–F69 are **unchanged** by this ADR — they
   are separate rulings and must not be inferred from this one.
5. **Reversing this decision requires a new superseding ADR**, including an explicit
   acceptance of the retrofit cost described below. This ADR is not to be re-litigated
   without one.

## Alternatives considered

- **Build hosted multi-tenant SaaS now.** Rejected: its prerequisites (per-tenant keys,
  schema/row isolation, REST authentication, API rate limiting) are the largest remaining
  engineering item in the repository, and the commercial track that would justify the spend —
  real Stripe billing plus customer willingness-to-pay evidence — is itself on hold by
  director ruling (2026-10-20, #165). Paying for isolation before validating that anyone will
  pay for the product inverts the order of work.
- **Half-way: keep the `user_id` boundary and add isolation incrementally.** Rejected on
  evidence: this is precisely the failure mode the 2026-10-30 audit catalogued — *declared
  enforcement level systematically higher than actual wiring* (G4/G5, D1–D3, `ax_metrics`,
  `frequency_gate`). A boundary that is documented but not enforced is worse than one that is
  explicitly absent, because agents have no prior that documentation may overstate.
- **Single-tenant, documented as such (chosen).** Zero engineering cost now; the boundary is
  stated where agents will read it, and the residual exposure is a known, recorded risk.

## Consequences

**Easier**

- The structural-debt work (#580–#588) can be judged against a single shape: single-node
  SQLite, one local process, no tenant context to thread through `collectors/`, `mcp/`,
  `output/`.
- `actor` and `user_id` can be documented honestly as audit attribution and data scoping,
  instead of being defended as security boundaries.
- Future service-shaped proposals now have a citable answer, which stops the periodic
  re-litigation of "should we isolate tenants?".

**Harder / accepted**

- If the product later goes hosted, per-tenant key management, schema or row isolation,
  authentication, and API rate limiting all become prerequisites at once, and the retrofit
  cost is strictly higher than building them up front. This cost is accepted deliberately.

**Obligations**

- `expectations.md` §3.17 F58 → `out-of-scope`, rationale pointing here (recorded in the same
  change as this ADR).
- `multi-tenancy-auth.md` carries a decision banner superseding its "planned / gated on SSE
  transport" statements.
- **Residual risk to track:** `src/autoinfo/api/server.py:100` `allow_origins=["*"]` is safe
  only while the bind address is loopback. Follow-up: emit a startup warning (or refuse to
  start) when `host` is not a loopback address. Not yet filed as an issue — recorded here so
  it is not lost.
- `AGENTS.md` and `GOVERNANCE.md` need no edit: neither promises tenancy anywhere.
