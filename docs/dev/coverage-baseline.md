# Coverage matrix — reproducible baseline

The end-user coverage matrix (`scripts/coverage_matrix.py`) has been published
with mutually inconsistent numbers. This page records every published figure
with the command that produced it, so a reader can tell a real change from a
different invocation.

**The rule that explains most of the drift:** `--evidence outputs` scans only
the generated artifacts. `collections/` and `knowledge/` live at the repository
root, so the `SOURCE_COVERAGE` and `KB_TIER_COVERAGE` sections are **inert**
for that invocation. Only `--evidence .` can measure sources and KB tiers.
The script now prints a warning to stderr when it detects the inert case.

All commands are run from the repository root.

## Published figures

| Baseline | Command | produced | gap | unconfigured | n/a |
|---|---|---|---|---|---|
| Stale committed report (`outputs/coverage-matrix/matrix-report.md`, 2026-08-13) | `python3 scripts/coverage_matrix.py --spec docs/dev/specs/end-user-matrix.yaml --evidence . --no-llm --output outputs/coverage-matrix/` | 26 | 176 | 149 | 481 |
| Delivery package (`pkg-AutoInfo/README.md`, 2026-10-26) | `.venv/bin/python scripts/coverage_matrix.py --evidence outputs --output /tmp/cov.md` | 29 | 322 | 0 | 481 |
| This machine, before the measurement fix (`335a7c3f`), raw | `.venv/bin/python scripts/coverage_matrix.py --evidence . --llm-available --output /tmp/cov.md` | 48 | 304 | 0 | 480 |
| This machine, before the measurement fix, corrected for the `column/video` fixture | same command, discounting the 16-byte fixture | 47 | 304 | 0 | 481 |

The 26/176/149/481 row is reproducible only against the evidence tree of that
date; the 29/322/0/481 row was produced on a different machine state and is not
reproducible from this tree. Both are recorded here as history, not as a target.

`--llm-available` is what forces `unconfigured = 0`. Without the flag the script
detects the key; with `AUTOINFO_LLM_API_KEY` unset it now reports
`unconfigured: 136` (the LLM-gated cells) instead of treating the unresolved
`${AUTOINFO_LLM_API_KEY}` placeholder as a real key.

## After measurement integrity (branch `fix/measurement-integrity`)

| State | Command | scanned cells | produced | gap | unconfigured | n/a |
|---|---|---|---|---|---|---|
| After accepting date-only stamps (T1) | `.venv/bin/python scripts/coverage_matrix.py --evidence . --llm-available --output /tmp/cov.md` | 66 | 52 | 300 | 0 | 480 |
| After purging the 10 fixture artifacts (T3) | `.venv/bin/python scripts/coverage_matrix.py --evidence . --llm-available --output /tmp/cov.md` | 65 | 51 | 300 | 0 | 481 |
| After purging, key absent (detected) | `.venv/bin/python scripts/coverage_matrix.py --evidence . --output /tmp/cov.md` | 65 | 51 | 164 | 136 | 481 |

The date-only fix adds 14 distinct produced cells (20 artifacts, 10 of them in
`ai-demo`, which is not a matrix domain; 4 of the medical-research cells were
new). Purging the fixtures removes one produced cell — `medical-research /
column / video` — which was a fixture-only fiction in a cell the spec marks
`not-implemented`, so it moves to `not-applicable` (n/a 480 → 481).

The plan expected 47 produced after the purge. The measured figure is **51**:
`presentation/markdown`, `tutorial/markdown`, and `column/markdown` all have
real timestamped artifacts on this tree, and `gaming/column/markdown` has real
artifacts from 2026-10-03. `medical-research/column/video` was the only
fixture-only cell.

## Reproduce

```bash
# Full measurement (sources + KB tiers are live)
.venv/bin/python scripts/coverage_matrix.py --evidence . \
    --output outputs/coverage-matrix/

# Artifact-only measurement (sources + KB sections are inert; warns on stderr)
.venv/bin/python scripts/coverage_matrix.py --evidence outputs \
    --output /tmp/cov.md
```

Same tree + same command ⇒ same numbers. The report records its evidence dir,
LLM availability, and generation timestamp in the header.
