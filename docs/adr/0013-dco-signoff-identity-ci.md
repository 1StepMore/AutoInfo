<!-- doc-type: adr -->
# 0013. DCO sign-off identity is enforced in CI (sign-off == author)

- **Status**: Accepted
- **Date**: 2026-11-07
- **Author**: Maintainer (governance remediation plan 2026-11-06, T10)

## Context

ADR-0009 settled that a DCO sign-off mismatch on a squash-merged commit is a
GitHub merge artifact to document, never an excuse to rewrite history, and
that contributors keep signing their own commits with `git commit -s`. What
0009 deliberately left open was the enforcement side: nothing in CI verified
that a PR's commits carry a sign-off at all, or that the signer is the commit
author. AutoInfo is agent-operated — commits are pushed under the repository
owner account by coding agents — so an unsigned or third-party-signed commit
would be indistinguishable from an attested one until a human read the log.

## Decision

1. Every commit in a PR range must carry a `Signed-off-by` trailer **whose
   identity equals the commit author** (bot, merge and noreply authors are
   exempt). This is judged only over the event's commit range — history is
   never re-litigated.
2. The judge is `scripts/check_signoff_identity.py`, run by the `lint` job in
   `.github/workflows/ci.yml`. It is a required status check (via the `DCO`
   check plus this script's exit code in the same job).
3. After a squash merge, GitHub rewriting the author to the merger account
   while keeping the contributor's trailer verbatim remains expected behavior
   (ADR-0009); the identity rule applies to commits as pushed to the PR
   branch, not to GitHub's merge artifacts.

## Alternatives considered

- **Probot DCO app only**: it checks trailer presence but not the
  author-equality edge cases the repo cares about (bot authors, merge
  commits), and cannot encode the range rules. Rejected as the sole gate; the
  app stays for the redundant presence check.
- **Server-side commit signing (gpg/SSH)**: stronger attestation, but every
  agent runtime would need key provisioning, which conflicts with the BYOK /
  low-ceremony agent model. Rejected for now.

## Consequences

- A PR with an unsigned commit fails CI before review, instead of being
  discovered in the log later (the #427 failure mode).
- Legitimate automation must either sign as the author it acts for or fall
  under the bot exemption — no third identity may sign.
- ADR-0009 remains the authority on squash-merge mismatch interpretation; the
  two decisions compose: 0009 interprets, 0013 enforces at push time.
