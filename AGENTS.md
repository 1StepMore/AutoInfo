# AutoInfo — Agent Guide

> Root instruction **index** — rules + pointers, not a corpus (#671; adherence ceiling ~200 lines,
> `docs/dev/agent-era-doc-architecture.md` §1). Detail loads on demand: repo layout → `docs/dev/repo-map.md` ·
> LLM setup → `docs/dev/llm-config.md` · gates/pipeline → `docs/dev/specs/` · examples → `docs/dev/mcp-usage-examples.md`.

## What Is AutoInfo

AutoInfo is a **universal information tracking and knowledge base platform**: configure sources
and topics; it handles collection, LLM-based structured extraction, summarization, and builds a
queryable knowledge base. **Domain-agnostic** — demo domains are configurations, not features.

## Agent Operating Model

**Agent-first**: the human director communicates intent in natural language → you translate
to MCP tool calls (stdio server). All capabilities are MCP tools (counts: `README.md` →
Status table). CLI mirrors MCP — `--domain X --topic Y` maps 1:1 to tool parameters.

## §0 安全条款（不可覆盖 · overrides every layer below）

1. **疑似密钥/凭据泄露**：立即停止动作，上报文件路径，不读取、不扩散、不存储内容。
2. **不管理原始 API key**：仅经 `configure_llm()` 的 `${ENV}` 引用（BYOK），永不落库落盘。
3. **03-Wiki append-only**：降级/删除非 agent 操作（详见 MUST NOT）。
4. **`.agents/expectations/` 期望工件仅 Owner 显式指令可改**；Tester 不得改代码或改期望使套件变绿。
5. 本节优先级高于下方 tiebreaker 的任何层级，任何指令不可覆盖。
6. **跨仓边界**：`AutoMedia` / `Omni` 三模块 / `e2e-test-suite` 是别的产品线，不是本仓模块、夹具或依赖——不改对方仓、不在对方仓开 PR/issue，其 issue/PR/backlog 永不是本仓作业项（即使本文件提到）；细则见 `docs/dev/repo-boundary.md`。
## 角色路由与冲突优先级

**角色由 Owner 显式指派，禁止自猜**（agents.md FAQ："explicit user chat prompts override everything"）。
角色不明、或指令与契约冲突且 tiebreaker 无法裁决 → 停止一切动作，输出 `ESCALATE: <原因>`。

| Owner 显式指派 | 角色契约（唯一事实源） | 固定返回格式 |
|---|---|---|
| Coder（实现） | `.agents/roles/coder.md` | PR 四段式 |
| Maintainer（裁决） | `.agents/roles/maintainer.md` | 裁决三选一 + 依据 + 后续 |
| Tester（验收） | `.agents/roles/tester.md` | 固定 JSON verdict |
| User（旅程验收） | `.agents/roles/user.md` | issue 四段式 |

**Tiebreaker**：直接指令（Owner 当前任务） > 角色文件 > 目录 scope（最近 `AGENTS.md`） > 根默认；
例外：§0 安全条款高于一切。「角色文件 > 目录 scope」是仓库本地约定，约束不了只机械加载最近
文件的极简 Harness → **硬边界靠 CI 权限事实与 rulesets 兜底，不能只靠提示词**。

## Quick Start & CLI

```bash
python -m autoinfo.mcp.server               # MCP stdio server (agent-facing; never interactive)
autoinfo init --demo medical-research       # scaffold a demo domain
autoinfo collect --domain medical-research  # fetch items (live per-source progress lines)
autoinfo process --domain medical-research  # LLM extraction + quality gates (G4/G5 opt-in — see gates)
```

**确定性命令（单一声明；CI 引用不重写）**：`BUILD_CMD=pip install -e ".[dev,ebook]"` ·
`TEST_CMD=pytest -m "not real_api" -q` · `LINT_CMD=ruff check src/ tests/ && mypy src/`。

MCP client configs committed: `.cursor/mcp.json` · `.opencode/mcp.json` · Claude Desktop per
`docs/dev/llm-config.md`. CLI: `autoinfo <cmd>` / `python -m autoinfo.cli <cmd>`; the MCP
server speaks JSON-RPC — never interactive.

## Architecture Rules

Hard constraints derived from `docs/dev/founder-expectations.md` (the *why* lives in
`docs/adr/`). Violating them produces incorrect behavior.

### KB Pipeline

`Collected Item → 01-Raw (sole entry, auto-ingest) → 02-Draft (from Raw only) → 03-Wiki (agent promotes)`.

| Rule | Why |
|------|-----|
| **01-Raw is the sole entry point** for all collected content | Every collected item must have complete source provenance; no skipping |
| **Agent cannot create Draft from outside** — only from 01-Raw | Prevents garbage entries; Raw→Draft→Wiki is sequential |
| **Agent promotes Draft→Wiki via `promote_kb_draft`** | Production step executed by the agent, no human gate (director decision 2026-08-08; ADR-0002) |
| **03-Wiki is append-only** | Demotion/deletion are not agent operations; tag `status: deprecated` only upon explicit human command |
| **Source metadata is mandatory** | Every Raw entry must have `source_url`, `source_type`, `source_platform` |
| **Product-analysis metadata** | Per-product fields persist in `custom_fields["product_analysis"]`; filterable via `search_knowledge_base(filter_custom_fields=...)` |

Full KB/collection pipeline detail: `docs/dev/specs/pipeline.md` §1–2; rationale:
`docs/adr/0001`, `docs/adr/0002`.

### Collection Pipeline

Two phases: `collect`（并行 handler → raw cache to `collections/` → dedup URL→PMID/DOI→fuzzy title→event→log），
then `process`（per-task model config → quality gates → 01-Raw entries）. Every handler implements the
`Collector` ABC's `fetch_items(ctx)` contract via `collectors/registry.py` — 加源 = 一个类 + 一次注册，
never a dispatch-chain edit.

### Quality Gates

| Gate | Type | Action on failure |
|------|------|-------------------|
| G0: Schema integrity | 🔴 Hard | block (no retry; deterministic check, retrying cannot change the result; item written to `_failed/`) |
| G1: Source authority (tier check) | 🟡 Soft | configurable: archive/flag/pass |
| G2: Dedup (URL + fuzzy title) | 🟡 Soft | configurable: archive/flag/pass |
| G3: Relevance scoring (0-100) | 🟡 Soft | configurable: archive/flag/pass (below threshold) |
| G4: Factual consistency | 🔴 Hard | 3× retry with escalating context → block |
| G5: Translation accuracy | 🟡 Soft | configurable: archive/flag/pass |
| G7: Entity-fact consistency | 🟡 Soft | default flag (deterministic, no LLM); per-domain `block`; honest hedges never flagged |
| D1: Product completeness / D2: Format integrity | 🔴 Hard | block delivery |
| D3: Freshness | 🟡 Soft | configurable threshold |

- **Default activation** — 上表说明 gate *做什么*，此条说明 *何时跑*：G0/G1/G2/G3/G7 默认 process 时跑；
  **G4/G5 是 opt-in**（CLI `--check-factual`/`--check-translation`；MCP 同名参数，default `false`）——
  G4 另在 Draft→Wiki CurationGate 无条件跑。D1-D3 仅在配置了 `delivery_gates` 处跑——出厂默认与全部
  demo 域均未配置，**交付门禁默认关闭**（decision point A, `docs/dev/plans/agent-infra-remediation-2026-10-30.md`）。
- Full gate catalog + configuration + testing strategy: `docs/dev/specs/quality-gates.md`.

### Product QC — 3-Layer Model (issue #194)

- **L0 dead-code gate**（default, blocking）: `make validate DIR=outputs/<domain>`（or
  `python3 scripts/quality_gate.py <dir>`）— deterministic structural checks（F1 空壳, F2 占位符,
  F3 双引用, F4 禁词, C1 造假条目, C2 日志泄漏, C3 CJK 残留, C4 截断行, C5 源完整性, C6 叙事接地
  #192, X1 跨产物实体冲突）. Exit 0/1/2.
- **L1 agent battery**（opt-in `--semantic`）: `scripts/agent_review/battery.py` — L0 不可见的残留
  语义盲点判定；verdict 必带证据；unreachable/unparseable ⇒ **ESCALATE, never PASS**（#195）. Manifest:
  `scripts/agent_review/blindspots.yaml`. 经 `config.llm` 厂商无关（capability-probed structured
  output, else deterministic markdown parsing）。
- **ESCALATE (human)**: value/intent calls go to the human director — never machine-final
  for subjective calls.
- **Single-production discipline**: a product is produced ONCE; QC (L0 → opt-in L1 →
  ESCALATE) is the arbiter. No regenerate-and-select ("best of N" reintroduces hidden
  selection bias). A failed gate ⇒ ONE constrained regeneration (defect fed back), re-gate.
- **Honest hedges are PASS**: "not disclosed in the available sources" is CORRECT behavior
  (#179/#191) — never flag it.

## Agent Constraints (MUST NOT)

| Action | Reason |
|--------|--------|
| Run the CLI `init` in agent workflows | Use the `init_project` MCP tool; CLI `init` remains for humans |
| Manage raw API keys | Use `configure_llm()` for BYOK — stores an env-var reference (`${AUTOINFO_LLM_API_KEY}`), never the raw key; never store/generate/transmit keys |
| Demote or delete Wiki entries | 03-Wiki is append-only; `deprecated` tag only upon explicit human command |
| Create Draft from outside 01-Raw | Draft must come from 01-Raw |
| Delete source or domain config | Human decides what sources/domains to remove |
| Modify `.autoinfo/config.yaml` directly | Use MCP tools (`add_source`, `add_topic`) |
| Run `autoinfo doctor` | Use `diagnose_system()` — returns structured health data |

## Merging a PR (MUST)

Each rule exists because its absence produced a specific failure (two agents write here).

| Rule | Why |
|------|-----|
| **Rebase onto the latest `origin/main` before merging** | `strict_required_status_checks_policy: true`; with two writers a stale-base merge can be textually clean yet semantically wrong — the rebase makes CI test the real merge result |
| **Merge with `--squash` only** | The ruleset allows no other merge method |
| **Expect no human approval gate** | `required_approving_review_count` is 0; GitHub forbids self-approval and agents push under the repo owner account — approval lives in the director's instruction |
| **Sign off every commit** | DCO (`Signed-off-by` trailer; `git commit -s`; ADR-0009; identity enforcement ADR-0013) |
| **Prefer fewer, larger PRs** | The release PR auto-merges minutes after any push to `main`, invalidating open PRs — budget ~20 min rebase CI cycle |

## Tool Discovery & Response Format

Discovery: `health_check()` → `tools/list` → `list_domains()` → `get_domain_schema(domain)`
→ `list_available_models()` → `list_output_templates(domain)`. Full catalog: `README.md`（单源）.
All tools return `{success: true, data}` 或 `{success: false, error: {code, message, actionable}}`
（ADR-0005）；无缓存项的 `process_collection` → `{status: "noop"}`. Worked patterns:
`docs/dev/mcp-usage-examples.md`.

## LLM Configuration (essentials)

- **Precedence**: MCP 参数 → `.autoinfo/config.yaml llm.*` → `AUTOINFO_LLM_API_KEY` → 默认（openrouter/deepseek-chat）。
- **Judgment calls**（G4/G5/llm_judge）resolve **config-first**（#195）：`llm.judgment_model` → `llm.model`，无硬编码模型常量。
- **Fallback chain**：跨端点 fallback 必须携带自己的 `${ENV}` 引用，绝不继承 primary key。
- Full setup（env 表/`json_mode`/自定义端点/按任务路由）：**`docs/dev/llm-config.md`**。

## `.omo/` Workspace

`.omo/` = agent-orchestrator workspace（gitignored runtime scratch）。Agent 可**读**它恢复编排上下文；
永不当作 KB/sources/output，永不从 AutoInfo MCP 工具修改它。

## Runtime Artifacts vs Source Files

`src/`, `tests/`, `docs/`, repo metadata are **source** — the only source of truth for
behavior. `collections/`, `knowledge/`, `outputs/`, `mvp/`, `autoinfo.db`, `logs/`,
`.autoinfo/`, `.omo/` are gitignored **runtime state**. Never hand-edit runtime artifacts
to fix behavior — fix the source. Full per-path table: `docs/dev/repo-map.md`.

## Backlog Priority Triggers

某些 P1 项的等级由「该工作量是否继续发生」决定——触发条件命中时**等级自动回升，不需要重新评审**：

| 项 | 当前等级 | 回升触发 | 回升后 |
|:--|:--|:--|:--|
| collectors 层重构（30+ handler / 130+ 源） | P1 | 下一次**加源或加域**（`src/autoinfo/collectors/` 或域配置新增） | P0 |

## Status

All counts live in **`README.md` → Status table**（single source of truth; AGENTS.md is pointer-only）.
Regenerate: `python3 scripts/doc_inventory.py`; `--check` validates against code/CLI. Invariants:
Architecture Rules above + `docs/dev/acceptance-framework.md` (AC1-AC9).

## References

- `docs/dev/repo-map.md` — repo layout + runtime boundary · `docs/dev/llm-config.md` — full LLM setup · `docs/dev/harness-run-facts.md` — 运行环境/门禁顺序/缺 key 症状/已知坑
- `docs/dev/workflow-charter.md` — dev process（canonical methodology: `docs/dev/七阶段AI开发流程-用CodingAgent交付成品的方法论.md`; ADR-0006）
- `docs/dev/founder-expectations.md`（D3 index）· `docs/dev/specs/` · `docs/dev/cross-dimensional-catalog.md`（**keystone**）
- `docs/dev/acceptance-framework.md` — **keystone** acceptance (AC1-AC9) · `docs/adr/` · `docs/glossary.md` · `docs/demo-release-standard.md`
- `.agents/roles/` 四角色契约 · `.agents/expectations/INDEX.md` 期望入口 · `.agents/audit/INVENTORY.md` 文档地图（AUTO-GENERATED）· `.github/governance-contract.toml`（ADR-0014，`python -m autoinfo.gov` 是唯一治理入口）

## Community

`CONTRIBUTING.md` · `GOVERNANCE.md` · `CODE_OF_CONDUCT.md` · `SECURITY.md` · `.github/`（templates, CODEOWNERS, release gates）.
