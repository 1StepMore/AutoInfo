# Constitution — AutoInfo 不可违背原则

> **性质**：仓库本地契约（非 Spec-Kit CLI 产物；Owner 决策 6——只落本文件，不装 specify CLI；
> `.specify/memory/` 路径为方针 §2.1 骨架约定，Spec-Kit 当前 README 未逐字定义该路径，见方针 ⚠️ V08）。
> **来源纪律**：本文件零代拟——每条原则逐字抽自 Owner 既有文档并标注出处；抽取执行者 = Ops-Executor
>（2026-11-08 整改运行），**成品供 Owner 事后审核，可整块 revert**。
> **效力**：任何角色（Coder/Maintainer/Tester/User）与任何层级的指令冲突时，本文件所列原则不可被覆盖；
> 与根 `AGENTS.md` §0 安全条款同级（§0 是本原则 §1 的展开）。

## 1. 安全与诚实（最高优先）

1. "疑似密钥/凭据泄露：立即停止动作，上报文件路径，不读取、不扩散、不存储内容。" —— 根 `AGENTS.md` §0-1（2026-11-08 整改新增， Owner 拍板决策 9 授权落盘）
2. "Use `configure_llm()` for BYOK — stores an env-var reference (`${AUTOINFO_LLM_API_KEY}`), never the raw key; never store/generate/transmit keys" —— 根 `AGENTS.md` Agent Constraints (MUST NOT) 表 "Manage raw API keys" 行
3. "This document must candidly acknowledge what doesn't work yet"（诚实承认缺口）—— `docs/dev/founder-expectations.md` §1.2 Design Principles 表 "Honest about gaps" 行
4. 产品侧同源原则："honest hedges are PASS"、unreachable/unparseable 判定 ⇒ "ESCALATE, never PASS" —— 根 `AGENTS.md` Product QC 节（issue #195/#179/#191）

## 2. KB 管线不变量（逐字，源 = 根 `AGENTS.md` KB Pipeline 表）

1. "**01-Raw is the sole entry point** for all collected content" —— 同表第 1 行
2. "**Agent cannot create Draft from outside** — only from 01-Raw" —— 同表第 2 行
3. "**03-Wiki is append-only**；Demotion/deletion are not agent operations; tag `status: deprecated` only upon explicit human command" —— 同表第 4 行
4. "**Source metadata is mandatory**" —— 同表第 5 行

## 3. 平台性质与质量观（逐字，源 = `docs/dev/founder-expectations.md` §1.2 Design Principles 表）

1. "**Production-grade quality**: Quality is not advisory. Retry-first, block-last." —— 同表
2. "**Agent-native**: All capabilities exposed as MCP tools first. CLI is fallback." —— 同表
3. "**Universal by default**: The platform is domain-agnostic. Demo domains are configurations, not hardcoded features" —— 同表
4. "**BYOK**: Users bring their own LLM keys. No vendor lock-in." —— 同表
5. "**Source-first**: Quality of output is bounded by quality of sources." —— 同表
6. "**Knowledge as asset**: The accumulated knowledge base is the primary long-term asset, not the real-time feed" —— 同表

## 4. 期望与治理边界（Owner 决策授权，源 = 2026-11-08 治理方针 02 稿 §5.1 + 本仓 ruleset 事实）

1. "只有 Owner 的显式指令有权改期望"（`.agents/expectations/`）；Tester 不得为使套件变绿而改产品代码或改期望 —— 02 稿 §5.1（[本方针设计]，非官方逐字条文，Owner 2026-11-08 拍板采纳）
2. 合并门禁 = ruleset `main-protection` 十项必过 + squash-only + DCO 签名（远端事实，非本文件创设）—— 见 `docs/dev/agent-infrastructure-audit` 同期的 ruleset 取证与本仓 AGENTS.md "Merging a PR (MUST)"

## 5. 修订规则

- 本文件只可经 **Owner 显式指令**修改；修改须记 ADR 并同步根 `AGENTS.md` §0（若涉及安全条款）。
- 原则文本与其出处漂移时（出处文档先行修订），以出处文档为准并触发本文件修订。
