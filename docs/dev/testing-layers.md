# Testing Layers: The AutoInfo Validation Pyramid

> **Purpose.** This doc names the four layers of AutoInfo's validation pyramid and
> gives each one a home. It exists because T-B-06 (S2) found the unit / foundation
> layer had no named place: `tests/` held unit tests and the scenario library held
> behavioral checks, but nothing stated where the boundary between them was or how
> a new check should pick a layer. The pyramid shape itself comes from the
> methodology (`agent-oriented-design-mindset.md` §4.1). The health criteria that
> make it pass or fail come from `docs/dev/acceptance-framework.md` AC9.

The pyramid has four layers, ordered from the wide fast base to the narrow slow
top:

```
                    ┌─────────────────┐
                    │    red_team     │  Adversarial (Safety)
                    ├─────────────────┤
                    │      e2e        │  Real user tasks (Reality)
                    ├─────────────────┤
                    │   component     │  Integration (Tool calls, coordination)
                    ├─────────────────┤
                    │      unit       │  Foundation (schemas, args, formats)
                    └─────────────────┘
```

There are only these four. Adding a fifth or renaming one breaks both the
`PYRAMID_LAYERS` enum in `src/autoinfo/mcp/validation.py` and the 5×4
category×pyramid coverage matrix.

---

## 1. The four layers

| Layer | Methodology name | What it covers | Where it lives |
|-------|------------------|----------------|----------------|
| `unit` | Foundation | Prompts, schemas, argument shapes, enum membership, format validation. One unit under test, no subsystem wiring. | `tests/` unit tests (pytest) **and** scenarios tagged `pyramid_layer: unit` |
| `component` | Integration | One subsystem exercised through real calls: a single collector, the KB, one output family, one CLI command group. Tool calls and agent coordination. | scenarios tagged `pyramid_layer: component` |
| `e2e` | Reality | Real user tasks and multi-step workflows that cross subsystems: collect → process → KB, a full B1 journey, the REST endpoints. | scenarios tagged `pyramid_layer: e2e` |
| `red_team` | Safety | Adversarial intent: injection, prompt escape, exfiltration, tool-argument abuse, authorization bypass. | scenarios tagged `pyramid_layer: red_team` |

### `unit` (Foundation)

**Covers:** the smallest checkable facts. A single schema key, an enum value, an
argument name, a format string, a prompt-contract shape. A unit check fails for
exactly one reason, the unit under test.

**Lives in two places.** A pure code-level unit (a parser, a helper, a validator
function) lives in `tests/` as a fast pytest test. The same kind of check
expressed through the real MCP / CLI / REST surface lives in the scenario
library tagged `pyramid_layer: unit`. Both count toward the base of the pyramid;
the difference is the surface, not the layer.

**Choose it when:** the assertion can be made without a live server, a real
network call, or a second subsystem. If mocking one collaborator is enough, it is
a unit.

### `component` (Integration)

**Covers:** one subsystem used end to end through its real surface. A collector
that really fetches, the KB that really stores and reads back, an output family
that really renders, a CLI group that really runs. Agent coordination also sits
here when it stays inside one subsystem.

**Lives in:** the scenario library, tagged `pyramid_layer: component`. Component
checks are behavioral, so they run as scenarios, not as pytest tests.

**Choose it when:** the check needs a real call, but only against one subsystem.
If two or more subsystems have to agree, it is `e2e`.

### `e2e` (Reality)

**Covers:** a real multi-step workflow that crosses subsystem boundaries. The
canonical shape is collect → process → KB → output, or a full end-user lifecycle
from onboarding through delivery. The check proves the seams between subsystems
hold, not just each subsystem in isolation.

**Lives in:** the scenario library, tagged `pyramid_layer: e2e`.

**Choose it when:** the failure you are guarding against can only appear when two
subsystems interact (a frontmatter field written by processing and read by
search, a product rendered from KB entries, a trace that spans collection and
delivery). If one subsystem alone can fail this way, it is `component`.

### `red_team` (Safety)

**Covers:** adversarial intent. A malicious feed payload that tries to inject a
frontmatter key, a prompt that tries to escape its template, a citation path that
tries to exfiltrate a local file, a tool argument that tries to break an
allow-list, an authorization boundary that a non-director actor tries to cross.

**Lives in:** the scenario library, tagged `pyramid_layer: red_team`. The
red-team scenarios live in `src/autoinfo/mcp/scenarios/redteam-*.yaml` plus the
boundary-abuse regressions in `scenarios/regression/`.

**Choose it when:** the intent of the check is adversarial, not merely
structural. Adversarial intent takes precedence over the structural layer, so a
one-step schema attack is `red_team`, not `unit`.

---

## 2. Two homes: `tests/` and the scenario library

AC9 judges two layers separately, and this doc makes the split explicit.

| | `tests/` (pytest) | Scenario library (`src/autoinfo/mcp/scenarios/`) |
|--|-------------------|--------------------------------------------------|
| What it verifies | the code itself | the running system through real surfaces |
| Execution | in-process pytest, fast, mostly hermetic | real MCP / CLI / REST calls, `llm_assert` runs a real model |
| Naming | organized by subject, mirroring `src/` (`tests/kb/`, `tests/output/`, `tests/mcp/`, …); no `test_bug_*` filenames | per-scenario `name`, `category`, `pyramid_layer`, `pipeline_stage`, `user_level` |
| Layer metadata | implicit (subpackage + test kind) | required `pyramid_layer` field |
| Failure semantics | pytest pass / fail | `passed` / `failed` / `unconfigured`, where `unconfigured` is never a pass |
| Counts (live) | ~5021 collected tests | 143 scenarios |

The boundary rule:

- **Schema, prompt, format, and argument checks that need no live surface** live
  in `tests/` as fast unit tests. The AC9 criterion "the test pyramid holds"
  (unit tests dominate, integration and e2e are a minority) applies to this
  layer, and `tests/integration/` is the small cross-module minority.
- **Behavioral checks, anything that must run against a real surface**, live in
  the scenario library. This is the executable specification at the top of the
  pyramid (AC9 criterion 4): real-surface calls, `unconfigured` never passes,
  per-step trace, regression flywheel.
- A check that could be written in both places is written as a `tests/` unit for
  the fast deterministic guarantee, and (only if it is worth executing against
  the live system) as a scenario for the real-surface guarantee. One is not a
  substitute for the other.

---

## 3. The `pyramid_layer` field

`pyramid_layer` is a **required** top-level key on every scenario YAML. It was
added in Todo 8 (T-B-01 / T-B-02) and is defined once, in
`src/autoinfo/mcp/validation.py`:

```python
PYRAMID_LAYERS: frozenset[str] = frozenset(
    {"unit", "component", "e2e", "red_team"}
)
```

`load_scenarios()` rejects a scenario that is missing the key or that carries a
value outside the enum (the same enforcement as `pipeline_stage`, `user_level`,
and `category`). `list_validation_scenarios` surfaces the value per scenario.
The scenario-authoring contract documents the field in §1.2; the coverage report
is `scripts/category_pyramid_coverage.py`.

**Which value goes where:** pick the layer from the *scope of the check*, not
from the size of the YAML. One subsystem = `component`; two or more subsystems
in one flow = `e2e`; adversarial intent = `red_team`; a single schema / format /
argument fact = `unit`. Empty cells are allowed and recorded: a 0-count cell is a
coverage gap, not a classification error. The report exits non-zero only when a
scenario cannot be placed at all (missing or out-of-enum value).

---

## 4. Live distribution (2026-09-13)

`python3 scripts/category_pyramid_coverage.py` scans every scenario YAML on disk
and reports the 5 categories × 4 layers matrix:

```
Category x pyramid coverage (5 x 4 = 20 cells)
========================================================================
category                    unit   component         e2e    red_team     total
happy_path                     5          60           5           0        70
edge_case                     16          33           0           2        51
failure                        1           7           0           5        13
agent_interaction              0           8           1           0         9
performance                    0           0           0           0         0
TOTAL                         22         108           6           7       143

Scenarios scanned  : 143
Cells populated    : 11/20
Cells empty (gap)  : 9/20
Unclassified       : 0
```

Reading the layer totals:

| Layer | Scenarios | Share of 143 | Shape |
|-------|----------:|-------------:|-------|
| `component` | 108 | 75.5% | the wide middle, one subsystem per scenario |
| `unit` | 22 | 15.4% | the foundation, schema / format / single-helper checks |
| `red_team` | 7 | 4.9% | adversarial safety checks (injection, escape, exfiltration, abuse, authorization) |
| `e2e` | 6 | 4.2% | cross-subsystem workflows |
| **total** | **143** | 100% | 0 unclassified |

Nine of the 20 category×layer cells are empty. That is a recorded coverage gap,
not an error: the `performance` category has no scenario yet (it is owned by
Todo 10), and several category / layer combinations are structurally unlikely
(for example, a `performance` `red_team` case). What AC9 forbids is a silent gap.
The report names every empty cell, and `Unclassified: 0` proves no scenario is
hiding outside the matrix.

The pyramid holds in the intended direction for the scenario library: the
integration middle (`component`) is widest, and the slow, expensive layers
(`e2e`, `red_team`) are the narrow top. The pytest layer carries its own
pyramid, with fast per-subject unit tests dominating and `tests/integration/` as
the small minority.

---

## 5. How this maps to AC9

AC9 ("Test and Validation Suite Health") grades two layers, and the four pyramid
layers are how each one is structured:

1. **The test layer** (`tests/`) is pyramid-shaped: fast unit tests dominate,
   integration and e2e tests are a minority, and external-dependency tests are
   gated. A layer inversion (more e2e than unit) is a RISK.
2. **The validation layer** (the scenario suite) is the executable specification
   at the top of the pyramid. Its `pyramid_layer` population is the *evidence*
   for AC9 criterion 3 and its per-cell coverage is the evidence for AC9
   criterion 4. `Unclassified: 0` and the named empty cells are the honest
   coverage statement that AC9 requires.

---

## 6. AX metrics gate (agent experience)

The pyramid says *where* checks live; the AX metrics say *whether the agent's
experience meets its pinned target*. Six metrics (plan §6, Todo 21) are measured
from live artifacts and gated by `scripts/ax_metrics.py` (exit non-zero on a
breach):

| ID | Metric | Target | Live source |
|----|--------|--------|-------------|
| M-01 | Task completion rate | >95% | newest suite run in the category×pyramid ledger |
| M-02 | Tool-call accuracy | >98% | `TOOL_SELECTION_OK` marker in a run trace |
| M-03 | Recovery success rate | >99% | `recover-*` scenario results + step `recovered` flags |
| M-04 | Documentation freshness | 100% | `scripts/doc_inventory.py --check` |
| M-05 | Token efficiency | ≤10% regression | deterministic token count of generated product text (keyless benchmark) vs the tracked `scripts/ax_token_baseline.json`; `llm_meta.tokens` additionally gated when present |
| M-06 | Error recovery time | <30s | duration of failed steps returning an actionable envelope |

A metric with no captured data reports `UNMEASURED` — it is never counted as a
pass. `python3 scripts/ax_metrics.py --record` seeds the deterministic,
LLM-free scenario subset that feeds M-01/M-02/M-03/M-06 before measuring; CI
runs exactly that (job `ax-metrics`). M-05 is additionally measured without an
LLM key: a fixed benchmark of real products is rendered through the real output
pipeline and tokenized deterministically, so the gate is active on a fresh
checkout. The pinned baseline is committed at `scripts/ax_token_baseline.json`
(refresh deliberately with `python3 scripts/ax_metrics.py
--update-token-baseline`; CI never auto-updates it).

## Related documents

- `docs/dev/validation-scenario-contract.md`: authoring contract for scenario
  YAML; §1.2 documents `pyramid_layer` alongside `pipeline_stage` / `user_level`
  / `category`.
- `docs/dev/acceptance-framework.md`: AC9 grades the test and validation layers;
  §9 defines the criteria and the evidence catalog entries (A22-A24).
- `src/autoinfo/mcp/validation.py`: `PYRAMID_LAYERS` and `SCENARIO_CATEGORIES`
  are the single source of truth for both enums.
- `scripts/category_pyramid_coverage.py`: the 20-cell coverage report, exit 1 on
  any unclassified scenario.
- `scripts/ax_metrics.py`: the six-metric AX gate (M-01..M-06), exit 1 on a
  breached threshold.
- `agent-oriented-design-mindset.md` §4.1 (methodology): the four-layer pyramid
  and the five scenario categories.
