# Capability matrix (product x format x domain)

- Generated: 2026-11-21T07:55:08+00:00
- Domains: retail
- Spec: docs/dev/specs/end-user-matrix.yaml
- Keyed/unkeyed split: keyed=1, unkeyed=0 (run key state: keyed)
- Gated/non-gated split: gated=0, non-gated=1
- Command: `'C:\Users\RenAnZai\AppData\Local\Programs\Python\Python313\python.exe' 'D:\贯维\AutoInfo\scripts\capability_matrix.py' --domains retail --only digest:markdown --force --out docs/dev/validation-reports/capability-27x3/issue-928-retail-verify`

Layers are cumulative and monotone: L2 implies L1, L3 implies L2.
A cell never reports L3 when L1 or L2 failed.
L3 means the model actually generated the artifact: a KB-derived fallback (LLM failure) reports L2-degraded and counts as a failure.

| Domain | Cell | Gated | Keyed | Reached | L1 | L2 | L3 | LLM | Duration (s) | Artifact | Detail |
|---|---|---|---|---|---|---|---|---|---|---|---|
| retail | digest:markdown | no | keyed | L3 | pass | pass | pass | llm | 62.564 | outputs/capability-matrix/retail/digest-markdown-20261121-075508-410592.md | bytes=19624; l2=pass; retry_policy=single-attempt, transient-only retry, never auth (1 attempt per cell; one retry only for transient/timeout errors); attempts=1 |
