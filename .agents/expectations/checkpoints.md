# Checkpoints — 离散检查点（评估终态，非逐步验证）

> 来源：02 稿 §8.2 + 本仓既有验收体系提抽（Owner 决策 5）。Tester 对指定目标逐条给出
> `pass|fail|blocked` + 证据（路径/命令输出/链接）；证据不可得 = blocked，不得编造。

| checkpoint | 应发生的状态变化 | 判定方式 |
|---|---|---|
| CP-AGENTS | 根 `AGENTS.md` 存在、≤200 行、含 §0 安全 + tiebreaker + 角色路由 + 确定性命令 | `.agents/scripts/consistency_check.py`（C3）+ 人工 |
| CP-CONTRACTS | 四契约四要素齐、≤30 行、薄适配器为指针非复本 | `.agents/scripts/consistency_check.py`（C4） |
| CP-INVENTORY | `.agents/audit/INVENTORY.md` 有 AUTO-GENERATED 头且与真实文档集一致 | `scripts/doc_inventory.py --check`（C6） |
| CP-NOPLACEHOLDER | 落盘治理文件零 `{{占位符}}` 残留 | `.agents/scripts/consistency_check.py`（C5） |
| CP-PARITY | REST 面与文档一致（canonical 8/8） | `scripts/surface_parity.py --check` |
| CP-DOCCOUNTS | README 计数与代码/CLI 一致（工具/场景/CLI 组） | `scripts/doc_inventory.py --check`（C1/C2 类事实） |
| CP-GATE-LIVE | 一致性校验 CI gate 生效：注入断链 → CI 必须挡住 | 确定性注入（PR 上实测） |
| CP-E2E | E2E 旅程基线可跑（挂验证场景） | PENDING-前置（GAP-01） |
