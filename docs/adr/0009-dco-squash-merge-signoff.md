<!-- doc-type: adr -->
# 0009. DCO squash-merge sign-off mismatch: document, do not rewrite

- **Status**: Accepted
- **Date**: 2026-10-01
- **Author**: Maintainer (issue #427)

## Context

Issue #427 reported that "the `Signed-off-by` email differs from the author
email, 17 of ~200 commits", which reads as a governance violation: contributors
signing off under an identity that is not theirs. The measurement did not
reproduce, and the implied severity was wrong on both counts.

**Measured facts.** At `1518bef7` the last 200 commits contain 123 with no
`Signed-off-by` trailer at all (pre-DCO history, merges, bot commits), 77 whose
trailer email matches the author, and 28 whose trailer email differs, two of the
28 being `dependabot[bot]`. Replaying the issue's own awk script at the issue's
own stated baseline `7385c5ad` yields 75 matching and 26 differing. The reported
"17" is therefore not reproducible at either baseline.

**Root cause: the squash merge, not a missing sign-off.** On the PR *branch*,
author equals sign-off. Verified concretely on PR #431: the branch commits carry
author `renanzai <renanzai@EVA-01.localdomain>` and a `Signed-off-by` trailer
with that identical email, and the DCO app passes them. Branch protection
requires squash-merge-only, so when GitHub squashes, it rewrites the new
commit's author to the merger account (`140780063+1StepMore@users.noreply.github.com`)
while carrying the branch's commit message body, and therefore the original
`Signed-off-by` trailer, through verbatim. On `main` the two emails then differ.

**DCO's default semantics already accommodate this.** The DCO app's documented
default mode is "presence + sign-off email matches the commit author", and it
explicitly excludes bots and merges from the identity comparison. It also never
evaluates the post-merge squash commit on `main`; it only checks the commits on
the pull request branch. The rows are therefore cosmetically inconsistent but
procedurally compliant, and the DCO check has been green on every recent PR.

**The repo never required identity matching.** `GOVERNANCE.md` and
`CONTRIBUTING.md` require only that commits *carry* a DCO sign-off (trailer
presence). Neither states that the sign-off identity must equal the author, and
there is no `.github/dco.yml`, so the app's default mode applies. The mismatch
was never a rule violation, which means the real defect was that it looked like
one to every reader of `git log`.

## Decision

**Document the artifact; change nothing enforceable.** Specifically: no
`.github/dco.yml`, no new commit hook, no CI check, and above all no history
rewrite.

- **Trailer presence is the enforced requirement.** A commit that lacks a
  `Signed-off-by` trailer is non-compliant and must be fixed.
- **An author/sign-off mismatch on a squash commit on `main` is accepted.** It is
  a faithful record of how the commit was created, not a defect.
- **Published history is never rewritten to reconcile it.** Amending or rebasing
  merged commits to "correct" the emails would destroy provenance and would also
  break the release-please commit-title chain.
- **Contributors sign their own commits** with `git commit -s`, using the same
  `user.name` / `user.email` identity they author with. A mismatch on a *branch*
  commit is a real problem, because that is what the DCO check evaluates.

The policy sentence now lives in the `### Squash merges and the
author/sign-off mismatch` subsection of the DCO section in `GOVERNANCE.md`, and
`CONTRIBUTING.md` carries a two-sentence pointer to it.

## Alternatives considered

- **Rewrite history to align the emails** (filter-repo, interactive rebase,
  re-sign the range): rejected — it would rewrite already-published commits
  shared with every clone, invalidate the release-please title chain, and
  destroy the very provenance the mismatch currently provides. The commit *is*
  the evidence that GitHub squash-merged it, and the merger author on the
  commit is part of the audit trail.
- **Force a single git identity so author and sign-off always match** (repo-level
  or global `user.email`): rejected — the divergence is introduced by GitHub's
  server-side squash, not by any local config. Setting a local identity changes
  nothing about the post-merge commit's author field, so the fix would be
  cosmetic and would not remove a single mismatched row.
- **Add `.github/dco.yml` / a hook to enforce identity match on `main`**: rejected
  — it would codify a rule the project does not have, force re-signing of
  legitimate history, and buy nothing: the DCO app already enforces the real
  requirement (branch commits must carry a matching sign-off) and has never
  failed.
- **Leave it undocumented**: rejected — an unexplained author/sign-off
  divergence in `git log` reads as a governance violation to every new
  contributor and reviewer, and invites a future "fix" that rewrites history.
  One paragraph plus an ADR is the entire cost of removing that misreading.

## Consequences

- The mismatched rows stay visible in `git log`. That is intended: they are
  historical facts, and the GOVERNANCE.md subsection explains them at the point
  where a reader is most likely to wonder.
- DCO stays green and unchanged. No new configuration file, hook, or workflow is
  introduced, so there is nothing new to maintain and no new failure mode.
- Contributors, agents, and reviewers have one place to look: the
  `GOVERNANCE.md` DCO subsection, backed by this ADR for the reasoning and the
  rejected alternatives.
- Issue #427's specific figure is recorded as unreproducible rather than
  quietly dropped, so a future audit does not re-derive the same wrong number.
- If the project ever moves off squash-merge-only branch protection, the
  divergence disappears on its own and this ADR should be revisited rather than
  amended (ADRs are append-only in spirit; see `docs/adr/README.md`).
