<!-- doc-type: adr -->
# 0014. A single machine-readable governance contract is the authority

- **Status**: Accepted
- **Date**: 2026-11-07
- **Author**: Maintainer (governance remediation plan 2026-11-06, T02/T10)

## Context

Governance knowledge was split across at least three carriers: prose
documents that each claimed to be the source of truth (with no precedence
order), enumerated blocklists in CI that only caught previously-seen drift,
and tribal knowledge about which surface wins when two documents disagree.
The same fact (a tool count, a scenario count) was restated in a dozen files
and drifted; "is everything OK right now?" had no single machine-answerable
judge; and decisions recorded in ADRs were not checked against the documents
that were supposed to implement them.

## Decision

1. `.github/governance-contract.toml` is the **single machine-readable
   governance contract**: authority order, derived facts and their scan
   patterns, scan exclusions (each with a written reason), gates with the
   8-state model, runtime profiles, platform, conflicts, and the
   decision-to-consumer registry.
2. When two surfaces state the same fact, the contract's `[authority].order`
   decides; `python -m autoinfo.gov adjudicate` makes that order executable.
   Derived (code-computed) facts always outrank any document.
3. Count-style facts are **derived from code, never declared**; documents
   restating them are scanned repo-wide (default-ON, exclusions need written
   reasons, per-line `counts-ignore` for dated records).
4. `python -m autoinfo.gov` is the **only entry point** for governance verbs;
   `autoinfo gov` and `scripts/gov.py` are thin forwards with zero business
   logic. There is no force-pass path anywhere in the stack.
5. Changes to the contract are PR-gated; semantic changes to authority,
   facts, gates or decisions additionally require an ADR (this one for the
   contract itself).

## Alternatives considered

- **Keep prose documents as truth and grow the CI blocklist**: rejected —
  the blocklist only catches previously-known stale strings (it missed
  "147 tools" surviving in keystone docs for weeks) and cannot answer <!-- counts-ignore: deliberately quoted historical stale value -->
  "what is true now".
- **Multiple per-domain contracts (docs contract, CI contract, …)**: rejected
  — the original problem was three unranked carriers; more contracts recreate
  it. One file, one precedence order.

## Consequences

- Adding a governance-shaped fact means editing the contract AND the deriver,
  in one PR; a contract typo fails `gov contract check` at CI time, not at
  first use.
- Documents stop being sources of truth and become views; the
  cross-dimensional catalog and friends are design snapshots whose live
  truth is `gov status`.
- The contract file becomes a single point of failure by design, which is
  why its structure and importability are validated on every PR (T02) and
  its semantics are covered by the negative-control harness (T17).
