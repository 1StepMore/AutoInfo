<!-- doc-type: adr -->
# 0008. Selective dependency upper bounds, no lock file

- **Status**: Accepted
- **Date**: 2026-10-01
- **Author**: Maintainer (issue #428)

## Context

`pyproject.toml` declares 38 concrete direct-dependency specifiers: 35 are
lower-bound-only (`>=`), 2 are bounded (`mcp>=1.0,<2.0`, `pytest>=8.0,<9`) and
1 is an exact pin (`ruff==0.16.8`). There is no lock file anywhere in the repo
(`uv.lock`, `poetry.lock`, `requirements*.txt`, constraints files are all
absent), and every CI install site is a bare floating resolve: seven `.[...]`
install invocations across four workflows plus the Dockerfile and the Makefile.
`uv` appears in the README only as an install accelerator
(`uv pip install -e .`), not as a lock workflow.

Both real-world breakages the project has suffered were **direct-dependency
major jumps**, each fixed after the fact by adding a bound: mcp 2.x broke
collection of 34 modules (#245), and pytest 9.1.1 removed
`EncodedFile.getvalue`, crashing caplog (#211). `.github/dependabot.yml` already
provides weekly pip + github-actions updates with major-version ignores for mcp
and pytest, so dependabot is the update mechanism — but it was only a partial
mitigation (it ignores bumps, it does not bound what CI installs). `SECURITY.md`
had no dependency policy at all.

## Decision

**Add selective upper bounds to the high-risk direct dependencies; do not add a
lock file.** Nine entries gain an upper bound (`httpx<0.29`, `fastapi<1.0`,
`uvicorn<1.0`, `litellm<2.0`, `trafilatura<3.0`, `lxml<7.0`,
`beautifulsoup4<5.0`, `sqlite-vec<0.2`, `stripe<16.0`); their lower bounds are
unchanged. All other direct dependencies — and all optional extras — keep their
existing constraints. Dependabot bound-bump PRs are how the bounds move.

### Why no lock file, concretely

- `requires-python` is `>=3.11` while CI runs **both** 3.11 and 3.12, so any
  universal lock must resolve under both interpreters at once — a constraint the
  current single-environment resolution never faced.
- There are seven bare install sites across four workflows plus a Dockerfile and
  a Makefile; adopting a lock means migrating every one and keeping them in
  sync, not just committing a file.
- A first lock freezes whatever resolved at lock time. A just-published bad
  release would be pinned in by the lock and must be caught by human review of
  the lock diff — a recurring audit cost for a solo-maintainer repo that the
  selective-bound approach avoids.

### Revisit triggers

This is a deliberate, revisitable decision. Re-open it when any of:

1. a third post-hoc bound addition lands (the incident-driven approach is not
   keeping pace), or
2. a cross-dependency version conflict appears that only a lock can resolve, or
3. an incident is traceable to a transitive float (the bound policy covers only
   direct deps, so a transitive break proves the coverage gap matters).

## Alternatives considered

- **Lock file (uv/poetry/pip-tools)**: rejected for now — the multi-interpreter
  resolution constraint, the seven install-site migration, and the first-lock
  freeze-in audit cost outweigh the reproducibility gain at this project size.
  Revisit per the triggers above.
- **Bound every direct dependency**: rejected — most direct deps are stable and
  bounds on them would generate dependabot churn with no incident to justify it.
  The policy is selective by design.
- **Do nothing (status quo)**: rejected — the two incidents show CI floating to
  a breaking direct-dep release, with the failures caught only after the fact.

## Consequences

- Dependabot becomes the sole update path; a bound bump arrives as a normal PR
  and is merged only if CI is green.
- Some security patches may wait for a bound-bump PR rather than flowing in
  automatically with a floating resolve — accepted, because the selective bounds
  cover only nine high-risk deps.
- `tests/test_dependency_bounds.py` locks the policy: every high-risk dep must
  carry a `<`, and a later bound bump cannot silently raise a floor.
- `SECURITY.md` documents the policy and points here for the no-lock decision
  and its revisit triggers.
