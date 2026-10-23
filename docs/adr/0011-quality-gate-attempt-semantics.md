<!-- doc-type: adr -->
# 0011. Quality-gate retry semantics: `retries` counts extra attempts

- **Status**: Accepted
- **Date**: 2026-10-24
- **Author**: Agent (Sisyphus), directed by B3

## Context

Issue #583 unified the quality-gate execution paths, and #565 exposed a
docs/code drift around retries. Two ambiguities had accumulated:

1. `QualityGateConfig.retries` was read differently by different gates. G0
   (deterministic schema check) shipped `retries=1`, which meant two attempts
   even though a second attempt cannot turn an invalid document valid. G4
   (LLM-judged factual consistency) shipped `retries=3`, but the docs and the
   code disagreed on whether that meant three total attempts or three *extra*
   attempts.
2. G4/G5 had more than one entry point, so retry and degradation behavior could
   drift between the process path and the standalone gate API.

A deterministic gate retrying is not just wasted work: it doubles the latency
and log noise for every malformed item while adding no information.

## Decision

`retries` means **extra attempts after the first one**. Total attempts are
`1 + max(retries, 0)`.

- **G0**: `retries=0` — exactly one attempt, then block on failure.
- **G4**: `retries=3` — four attempts total, then block and write `_failed/`
  diagnostics.
- A single `retry_with_escalation` helper implements the contract, and
  `run_quality_gates` resolves gates through one registry instead of
  per-gate branches.
- G5 exposes one canonical core (`_run_translation_gates`, called by
  `check_translation_accuracy`); `process._run_g5` is only terminology
  resolution plus a defensive fallback.

The docs table reports the documented **Attempts** column as `1 + retries`, so
prose and configuration cannot drift again (locked by
`tests/quality/test_gate_retry_docs.py`).

## Alternatives considered

- **Keep `retries` as total attempts**: rejected — it reads naturally as
  "number of retries", and every existing config already used it as extra
  attempts. Reinterpreting it would silently change every configured gate.
- **Keep G0 at one retry**: rejected — schema validity is deterministic, so the
  second attempt is pure latency with zero new information.
- **Leave the duplicate G4/G5 entry points**: rejected — #583 exists precisely
  because duplicated paths drift; one core plus thin wrappers is the fix.
- **Make G0 configurable back to >0 retries**: still possible via per-domain
  config, but the default is now 0; a caller that explicitly sets retries gets
  the documented `1 + retries` behavior.

## Consequences

- G0 behavior changes from two attempts to one; G4 from three to four. Both are
  intentional and covered by regression tests (`test_g0_once.py`,
  `test_gate_registry.py`, `test_v1_5_quality_gates.py`).
- Configs that set `retries=3` now explicitly mean four attempts; the docs and
  AGENTS table state this.
- Phase 2 of #581/#582 can remove the remaining dispatch/wrapper code without
  touching gate semantics, because the contract now lives in one place.

## References

- Issues: #583, #565
- `docs/dev/specs/quality-gates.md` §2 (gate philosophy) and retry table
- `docs/dev/acceptance-framework.md` (attempts table)
- `src/autoinfo/quality.py` (`retry_with_escalation`, `Gate`)
