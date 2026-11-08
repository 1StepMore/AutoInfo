# DEBT — 技术债台账（Maintainer 维护）

> 唯一事实源。每条一行：`| ID | 描述 | 影响面(子系统ID) | 等级 | 登记日期 | 依据链接 |`。
> 既有登记承接 `docs/agent-infrastructure-audit-2026-10-30.md`（27 项判定）与
> `docs/dev/plans/agent-infra-remediation-2026-10-30.md`（决策点 A/B/C 待 Owner 拍板）。

| ID | 描述 | 影响面 | 等级 | 登记日期 | 依据 |
|---|---|---|---|---|---|
| DEBT-01 | `scripts/ax_metrics.py` CI/Makefile 零接线（audit #19 🔶）；门槛化依赖数据源恢复 | S-15 | P2 | 2026-11-08 | audit-2026-10-30 #19 |
| DEBT-02 | L1 agent battery 零接线（audit #11 🟡）：设计精良但无触发器 | S-15 | P2 | 2026-11-08 | audit-2026-10-30 #11 |
| DEBT-03 | E2E 可执行基线缺失（inventory GAP-01）：骨架已建，PENDING-前置 | S-14 | P1 | 2026-11-08 | inventory GAP-01 |
