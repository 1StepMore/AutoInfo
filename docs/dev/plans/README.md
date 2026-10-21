<!-- doc-type: plan-index -->
# Wave Plan Archive (docs/dev/plans/)

> **What this is**: the durable home for **major-wave** development plans.
> Per ADR-0006 + the workflow charter, wave-level planning normally lives in
> the gitignored orchestrator workspace (`.omo/plans/`) — ephemeral by design.
> **Major waves promote here on completion** (or on interruption, so a future
> session can resume them). This directory is the "PRD → durable" destination
> for the methodology's stage 4-5 artifacts.

## When a wave is "major" (promotion criteria)

Promote a wave plan to this directory when ANY of these holds:

1. **Cross-module blast radius** — the wave touches 2+ modules (e.g. a change
   spanning `collectors/` and `mcp/`, or `cli/` and `output/`).
2. **Public interface change** — MCP tool surface, CLI command groups, REST
   envelope, storage schema, or LLM call paths that other code depends on.
3. **Multi-session work** — the wave is expected to span multiple agent
   sessions (high interruption risk; the decomposition must be reconstructable).

Small single-module waves stay in `.omo/plans/` — their value is distilled into
the ADR + CHANGELOG when done (stage-7 backfill), and promoting them adds noise.

## How to promote

1. Copy the finished plan from `.omo/plans/<wave>.md` to
   `docs/dev/plans/<wave>.md` (kebab-case, dated prefix optional).
2. Add the `<!-- doc-type: plan -->` marker to the head.
3. Append a short **Outcome** section: what shipped (commits/PR refs), what
   changed vs the plan, and which lessons backfilled where (ADR/skill/glossary).
4. If the wave was interrupted instead of finished: keep the plan as-is but
   mark clearly in the front matter (`<!-- status: interrupted -->`) and list
   the next un-done step at the top.
5. Regenerate the doc inventory: `python3 scripts/doc_inventory.py` + `--check`
   (must exit 0).

## NIGHTLY.md live zone is generated

NIGHTLY.md 的【活区】禁止手改 —— 改 `docs/dev/plans/nightly-ledger.jsonl` 后跑
`python scripts/nightly_ledger.py --write`。CI 会跑 `python scripts/nightly_ledger.py --check`。

- 台账 append-only，一行一个 JSON 事件；状态变更用 `supersedes` 追加新事件，不改旧行。
  两个夜间分支各自在 EOF 追加时，靠 `.gitattributes` 的 `merge=union` 合并（plain git 会把
  相邻的 EOF 插入判为冲突）。
- 四个活区块（`gap_snapshot` / `next_queue` / `friction_log` / `revision_requests`）
  由 `<!-- LEDGER:BEGIN <name> -->` / `<!-- LEDGER:END <name> -->` 包围，脚本只替换块内内容。
- 【冻结区】（完成定义 / 验收命令）不受脚本影响，逐字节不变。
- `scripts/nightly_gap.py` 只负责计算差距数据，可被台账的 `gap_snapshot` 事件引用。

## Relationship to other docs

| Doc | Answers |
|-----|---------|
| `docs/dev/workflow-charter.md` | The 7-stage process; where each stage's artifacts land |
| `docs/adr/0006-dev-process-workflow-charter.md` | Why this workflow was adopted |
| `.omo/plans/` | Runtime scratch for all waves (gitignored) — the un-promoted majority |

## Archive

| Wave | Type | Outcome | Status |
|------|------|---------|--------|
| `agent-oriented-gap-register.md` | Validation / agent-native gaps | Commit `2e1052d`: 62-gap agent-oriented register closed across 7 waves; scenarios 138→159; canonical envelope + `outputSchema` 100%; AX M-01..M-06 gated | completed |
