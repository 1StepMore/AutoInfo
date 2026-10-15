# AutoInfo Governance

This document describes how the AutoInfo open-source project is run. It is a
lightweight governance model for a small maintainer team, written in the
spirit of Minimum Viable Governance (MVG): process is added only when a
concrete pain point appears, and every rule here exists because a real problem
motivated it. When in doubt, prefer the lighter option.

## Project model

AutoInfo is an agent-first, domain-agnostic information tracking and knowledge
base platform. Users configure sources and topics; AutoInfo handles the rest:
automated collection, LLM-based structured extraction, summarization, and a
queryable knowledge base. It is MIT licensed and developed openly on GitHub.

### Roles

There are three roles, deliberately flat:

- **Maintainer**: a person (or small group of 1-3 people) with write access to
  the repository. Maintainers triage issues, review and merge pull requests,
  manage releases, and make final decisions. The maintainer team owns the
  project's direction.
- **Contributor**: anyone who opens an issue, comments, or submits a pull
  request. Contributions are welcome regardless of experience level. See
  `CONTRIBUTING.md` for how to contribute, and `CODE_OF_CONDUCT.md` for the
  standards every interaction must meet.
- **User**: anyone who runs AutoInfo or consumes its output. Users are not
  required to participate in development, but their feedback is the project's
  main compass.

## Decision-making

Maintainers make decisions by **lazy consensus**: a proposal is accepted once
it has been discussed and no maintainer has objected within a reasonable
period (usually 72 hours for non-trivial changes). Any maintainer may call a
vote. Objections must be specific and actionable rather than general
disagreement.

Non-trivial architecture decisions must be recorded as an Architecture
Decision Record (ADR) in `docs/adr/`, following `docs/adr/TEMPLATE.md`. The
ADR rules:

- **ADR numbers are never reused.** If a decision changes, write a new ADR.
- **Accepted ADRs are never rewritten in place.** If a decision is
  superseded, write a new ADR and mark the old one `Superseded by NNNN`.
- An ADR is required when a change alters an architecture rule (the KB
  pipeline, collection pipeline, quality gates, delivery), introduces a
  non-obvious trade-off, or has a wide blast radius (MCP surface, REST
  envelope, storage schema, LLM call paths).

## Issue triage

AutoInfo uses GitHub's default issue labels plus a small set of repo-specific
ones. Labels fall into four independent groups, and an issue may carry one
label from each:

| Group | Labels | Meaning |
|-------|--------|---------|
| **Kind** | `bug` | Definite defect, unexpected behavior |
| | `enhancement` | Improvement to an existing capability, or a new one |
| | `documentation` | Documentation defect or gap |
| | `tests` | Test-suite / CI defect |
| | `epic` | Umbrella issue tracking several independent sub-items |
| **Priority** | `priority/P1` | Blocks a release, a required status check, or the KB |
| | `priority/P2` | Significant, but not release-blocking |
| **Gate** | `needs-real-verification` | Closure is blocked until the fix is verified on real-product output (see below) |
| **Release** | `release:user-visible` | Change is user-visible even though its diff looks internal-only |
| | `release:skip` | Change is intentionally not released |
| | `autorelease:pending` / `autorelease:tagged` | Managed by release automation; do not set by hand |

Kind is the only group that is reliably present. Priority is set when the
issue needs an SLA; issues with no priority label are backlog.

`good-first-issue` and `help-wanted` are set by maintainers, not by reporters.
Security reports follow `SECURITY.md` instead of the normal triage flow.

> **Why no `needs-triage` status label.** An earlier revision of this
> document prescribed a four-group taxonomy (`needs-triage`,
> `triage/accepted`, `in-progress`, `kind/*`, `critical-urgent`, `backlog`,
> …). Measured against all 267 issues, **not one** of those labels was ever
> applied — the doc described an aspirational system that the repository
> never adopted, which made every triage a fresh judgment call. This section
> now documents the labels that are actually in use. If the richer taxonomy is
> ever wanted, land it as labels-first plus a backfill, not as prose.

## Response SLA

Maintainers commit to the open-source-guide baseline: every issue or pull
request receives a **human first response within 7 days** of being opened.
Beyond that baseline, first response is prioritized by the Priority label:

| Priority | First human response |
|----------|----------------------|
| `priority/P1` | within 24 hours |
| `priority/P2` | within 3 days |
| unlabeled (backlog) | within 14 days |

A response means a maintainer has acknowledged the report and said what
happens next, not necessarily that it is resolved. `SECURITY.md` overrides
these windows with faster commitments for vulnerability reports.

## Issue closure requires real-product evidence

A merged fix is not by itself proof that the reported defect is gone from the
products the project actually ships. Before closing an issue whose fix added or
changed a `validate` assertion (`src/autoinfo/validation_matrix.py`), run that
assertion over the real product tree:

```bash
python3 scripts/real_product_assertions.py --assertions <name> --issue N
```

- **Failures reported** → the flagged assertion is not cleared; keep the issue
  open and apply the `needs-real-verification` label.
- **Clean (exit 0)** → attach the generated `--md-out` / `--json-out` evidence
  to the issue as the close artifact.

The scanner is deterministic and offline (no LLM, no network); its exit code is
the gate (`0` = no P0/P1 failure, `1` = P0/P1 failures, `2` = usage error). This
closes the loop from issue #356: the maintainer never hand-scans real products
again.

## Stale policy

AutoInfo does **not** use an aggressive stale bot, and this is a deliberate,
documented decision. Community research is clear that auto-closing bots
backfire: Gradle retired its stale bot after community backlash, when issues
were closed automatically without a human ever weighing in. The cost of a few
quiet issues is lower than the cost of alienating reporters.

- **Initial state**: no stale bot. Issues and pull requests stay open until a
  human acts.
- **Revisit trigger**: adopt one only if abandoned pull requests pile up and
  the backlog becomes unmanageable.
- **If ever added**, the configuration must be conservative: mark after 360
  days, close only 30 days after marking, and always exempt `bug` and
  `good-first-issue` labels from both marking and closing.

## Pull request review policy

CI is the gatekeeper. Every pull request must pass the required status checks
in the `main-protection` ruleset (`.github/workflows/ci.yml`: `lint` (ruff),
`mypy-changed-files`, `test` (pytest); plus `Conventional Commits title`,
`Fast subset coverage on changed modules`, and `DCO`). Reviewers focus on
substance, not on style trivia that CI already covers.

- **Solo-maintainer mode**: AutoInfo currently runs with a single maintainer,
  so `required_approving_review_count` is `0` and the author can merge their
  own PR once CI is green. GitHub structurally blocks self-approval (an author
  cannot approve their own PR under either branch protection or rulesets), so
  a non-zero approval requirement would deadlock every merge. The CI gate is
  the review. When a second trusted maintainer joins, bump the approval count
  to `1` — no other change is needed.
- **Draft pull requests are assumed not ready.** Do not review a draft unless
  explicitly asked; a draft means the author wants feedback later.
- **Small pull requests are strongly preferred.** A request that takes more
  than a few hundred lines to review will likely be asked to split.
- **First-time contributors get extra warmth.** GitHub auto-classifies
  first-time contributors; the maintainer posts a welcome comment, points at
  `good-first-issue`, and walks through the process step by step. Reviewing a
  first PR is a teaching act, not just a gate.
- **Cross-cultural review guidance**: be explicit about what blocks the merge
  and what does not. Label blocking feedback separately from optional polish,
  for example `Blocking:` versus `Nit:`. Short, direct English can read as
  rude to non-native speakers; one sentence of context costs little and
  prevents friction.

## Merge strategy and branch protection

`main` is protected by the `main-protection` **ruleset** (repository-level,
active, no bypass actors — even the repo owner cannot bypass):

- **A pull request before merging** — no direct pushes to `main`.
- **Approval count `0` (solo-maintainer mode)** — the author merges their own
  PR once all gates pass; see the review policy above.
- **Required status checks, strict** — `Lint`, `Mypy (changed files)`, `Test
  suite (fast subset)`, `Conventional Commits title`, `Fast subset coverage on
  changed modules`, `DCO`; branches must be up to date with `main` before
  merging.
- **Required review-thread resolution** — all conversations on the PR must be
  resolved before merge.
- **Squash-merge only** — every merged PR becomes one clean commit on `main`,
  keeping history linear and blame useful (matches GitHub's own recommendation
  for default-branch hygiene).
- **Force pushes and deletions blocked.**
- `CODEOWNERS` remains in place for auto-requesting reviews (the "Require
  review from Code Owners" enforcement is dormant while approval count is `0`;
  it activates automatically once a second maintainer exists and the count is
  raised).

## Developer Certificate of Origin (DCO)

All contributions require a sign-off: `git commit -s`, affirming the Developer
Certificate of Origin (<https://developercertificate.org/>). The DCO app
(<https://github.com/apps/dco>) enforces this check once installed; a pull
request whose commits lack sign-off fails the check until the author amends
them.

Sign-off exists for legal provenance. AutoInfo is MIT licensed, and
maintainers need a clear chain of who contributed what and under what
authority. A DCO is lighter than a Contributor License Agreement and is the
standard practice for MIT projects.

### Squash merges and the author/sign-off mismatch

`git log` on `main` shows commits whose `Signed-off-by` email differs from the
commit author email. Every one of them is an artifact of the squash merge
required by branch protection (see above), not a contributor who skipped the
sign-off:

- **On the PR branch, author equals sign-off.** Verified on PR #431: the branch
  commits carry author `renanzai <renanzai@EVA-01.localdomain>` and a
  `Signed-off-by` trailer with that identical email, so the DCO app passes them.
- **The squash merge creates the divergence.** GitHub rewrites the merged
  commit's author to the merger account (for example
  `140780063+1StepMore@users.noreply.github.com`) while the message body keeps
  the branch's `Signed-off-by` trailer verbatim. The two then differ on `main`.
- **The DCO check does not flag it.** The app's default mode is presence plus
  sign-off-email-matches-author, but it excludes bots and merges and it only
  ever evaluates the commits on the PR branch, never the post-merge squash
  commit. The DCO check has been green on every recent PR.

Measured on the last 200 commits at `1518bef7`: **123 carry no sign-off at
all** (pre-DCO history, merges, and bot commits), **77 carry one that matches
the author**, and **28 differ**, two of which are `dependabot[bot]`. Replaying
the original audit at its own stated baseline `7385c5ad` yields 75 and **26**.
The reported "17" therefore did not reproduce at either baseline.

Policy:

- **Trailer presence is the enforced requirement.** Both `GOVERNANCE.md` and
  `CONTRIBUTING.md` require that commits *carry* a DCO sign-off; neither states
  that the sign-off identity must equal the author, and the repo has no
  `.github/dco.yml`, so the app's default mode applies.
- **An author/sign-off mismatch on a squash commit is an accepted artifact.** It
  is cosmetically inconsistent, not procedurally non-compliant.
- **History must not be rewritten to reconcile it.** Amending or rebasing
  published commits to "correct" the emails would destroy provenance: the
  mismatch is an accurate record of how the commit was created.
- **A mismatch on a *branch* commit is a real problem.** That is what the DCO
  check evaluates, and it will fail. Sign your commits with the same identity
  you author with (`git commit -s`, with `user.name` / `user.email` set to the
  identity you intend to certify).

See [`docs/adr/0009-dco-squash-merge-signoff.md`](docs/adr/0009-dco-squash-merge-signoff.md)
for the full decision record.

## CODEOWNERS

`.github/CODEOWNERS` maps paths to owning maintainers. It auto-requests review
from the matching owners when a pull request touches their paths, and with the
"Require review from Code Owners" branch-protection setting it makes that
review mandatory. Pitfalls to remember:

- **Last match wins**: CODEOWNERS is processed in file order, and the most
  specific matching pattern determines the owner. Put broad patterns first.
- **Owners need write access**: entries must resolve to users or teams with
  write permission to the repository, or the auto-review request fails.

## Release management

Releases use **release-please** with **Conventional Commits**, producing
semantic versioning (semver) from commit messages:

- `feat:` bumps the minor version; `fix:` bumps the patch version; breaking
  changes (a `BREAKING CHANGE` footer or a `feat!:` prefix) bump the major
  version.
- release-please opens a **release PR** that batches the accumulated changes
  into a single release with a generated changelog. Maintainers review and
  merge it; merging tags the release and publishes the package.
- Feature work lands on `main` continuously. Only maintainers merge release
  PRs.

## Change control

Documentation changes that affect the acceptance framework or its evidence
catalog require director approval per AC7; they are not self-approvable. See
`docs/dev/acceptance-framework.md` for the acceptance mechanism (AC1-AC9)
and its change-control rules.
