# L0 / L1 quality baseline (before the matrix run)

Captured 2026-10-27 on `feat/capability-matrix-27x3`, after T3 deleted the ten
fixture artifacts. Raw output: `logs/l0-baseline-<domain>-2026-10-27.log`,
`logs/l1-baseline-medical-research-2026-10-27.log`.

## L0 — `scripts/quality_gate.py` (deterministic, blocking)

| Domain | Exit | Defects | Files with defects | Class histogram |
|---|---|---|---|---|
| medical-research | 1 | **55** | **52** | `H3` 46, `H2` 4, `F1` 2, `C4` 2, `F2` 1 |
| language-learning | 1 | 1 | 1 | `H3` 1 |
| ai-commercial | 2 (usage) | — | — | `IO no .md files under outputs/ai-commercial` |

`medical-research` reproduces the post-T3 figure **55 / 52** exactly. The pre-T3
figure (60 / 57) is superseded by T3's fixture deletion and is not reproduced —
recorded here so the two numbers are never mixed.

`ai-commercial` has no rendered `.md` at all (only `report-json-*` and
`report-video-*`), so the gate exits 2. That is a coverage absence, not a pass:
the matrix run in T17 is what gives this domain rendered products to gate.

No defect was fixed and no class was silenced to obtain these numbers. Both
`H3` bullets-serialization-glue (46) and `H2` word-boundary truncation (4) are
pre-existing rendering defects; they are registered in
`docs/known-limitations/demo-quality-residuals.md` by T18, not repaired here.

## L1 — `scripts/agent_review/battery.py --semantic` (opt-in, semantic)

`outputs/medical-research`, exit **1**:

```
L1 battery — outputs/medical-research
L0 defects: 55
Worklist: 1 item(s)
  [ESCALATE] cross-product-entity-consistency (all): LLM channel unreachable:
             All LLM models (primary + fallback) failed: openai/Qwen3.8-27B, ...
Honesty: ['cross-product-entity-consistency (all)']
SUMMARY: 0 PASS / 0 FLAG / 1 ESCALATE
```

Verdict is `ESCALATE`, not `PASS` — the battery refused to sign off a dimension it
could not judge, which is the documented behaviour (#195: unreachable judgment
escalates, never passes). Root cause is the same missing `AUTOINFO_LLM_API_KEY`
as T12/T13 (`logs/blockers-2026-10-27.md`). Three retries were attempted by the
LLM layer, then it surfaced the auth error.

Consequence for T17/T18: every cell whose verdict depends on L1 semantic judging
is reported as `L1 unreachable (no key)`, never as verified.

## Reproduction

```bash
.venv/bin/python scripts/quality_gate.py outputs/medical-research        # exit 1, 55/52
.venv/bin/python scripts/quality_gate.py outputs/language-learning       # exit 1, 1/1
.venv/bin/python scripts/quality_gate.py outputs/ai-commercial           # exit 2, no .md
.venv/bin/python scripts/agent_review/battery.py outputs/medical-research --semantic  # exit 1, 1 ESCALATE
```
