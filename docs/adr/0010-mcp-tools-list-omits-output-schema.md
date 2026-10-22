# 0010 — `tools/list` omits the shared `outputSchema`

- **Status**: Accepted
- **Date**: 2026-10-22
- **Deciders**: director (owner) + coding agent
- **Related**: ADR 0005 (unified envelope), #562, #577, #581, #588

## Context

Every MCP tool declared `outputSchema` = the same canonical envelope
(`{success, data}` / `{success, error}`). 149 copies of one schema were sent in
every `tools/list` response:

- director wire payload: 244,289 B / 52,495 cl100k tokens;
- `outputSchema` accounted for 143,040 B = **58.6%** of it;
- distinct schema values: **1**;
- `scripts/ax_metrics.py` M-05 measures generated product text, not tool
  declarations, so the cost was invisible to the AX gate.

## Decision

1. `tools/list` no longer advertises `outputSchema` on any tool.
2. The envelope remains a documented contract in `docs/dev/specs/mcp-tools.md`
   (and ADR 0005); the server still returns it.
3. Per-tool `outputSchema` is a follow-up for ~10 high-value write/complex
   tools, after the tool registry split (#581) makes schema/handler colocation
   enforceable.
4. `scripts/tool_desc_audit.py` guards against re-adding the shared schema
   (`legacy_output_schema_wrapped` must stay `False`) and reports the count of
   explicit per-tool schemas.

## Consequences

- Director wire payload drops to 101,249 B / 21,804 cl100k (−58.6%).
- Agents lose a machine-readable return declaration they never used for
  per-tool branching (all copies were identical); the envelope is still
  documented once.
- Re-introducing a shared schema is now a test failure, not a silent 58.6% tax.
- A future per-tool schema must be attached explicitly (`Tool(outputSchema=…)`),
  which the audit counts.

## Alternatives rejected

- Keep the shared schema and document the cost (status quo): continues to pay
  58.6% per session with zero information gain.
- Write all 149 per-tool schemas now: high maintenance and drift risk before
  #581 colocates schema and handler.
