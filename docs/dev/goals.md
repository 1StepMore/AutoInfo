# 目标阶梯（当前目标 / 达标判据 / 下一阶段）

<!-- goal-cmd: python3 scripts/goal_matrix_quality.py -->
<!-- 约定：goal-cmd 退出码 0 = 当前目标达标；非 0 = 未达标；2 = 环境/用法错误（不算达标） -->

> 给任何 agent / harness：**每班开工先跑** `python3 scripts/agent/autonomy.py goal`。
> 返回 `ACTIVE` ⇒ 正常推进当前目标；返回 `ACHIEVED` ⇒ 按下面「达标之后做什么」四步走，然后停手。
> 判据必须是命令 + 退出码，不接受「我觉得差不多了」。

## 阶梯

| 阶段 | 目标 | 达标判据 | 状态 |
|:--|:--|:--|:--|
| **P1** | 生产矩阵 100% —— 21 个域 × 4 个条件（真语料 / 真产物 / 可溯源 / 无占位）全部达标 | `python3 scripts/nightly_gap.py` ⇒ **exit 0**（任一域任一条件不满足即 exit 1；真语料要求 ≥10 条且 7 天内有新采集，且 sources_ran > 0（空跑不算）） | `达标 ✅（exit 0 @ 2026-11-18，证据 #842；总裁决保留 owner）` |
| **P2** | 矩阵覆盖率 100%，且每个格子产出的东西质量合格；质量结论必须来自真模型（fake 仅限链路/契约/覆盖，记 confidence=mock）。Owner 2026-11-20 直接指令 | `python3 scripts/goal_matrix_quality.py` ⇒ **exit 0**（满格 0 missing/pending + 全 L3 + keyed 纪律 + L0 三域 exit 0 + L1 battery 全 PASS 真模型 + 证据 git 跟踪；比驱动器退出码更严，诚实 block 不算达标） | `ACTIVE` |

## 达标之后做什么（顺序固定，别省步骤）

1. `python3 scripts/agent/autonomy.py stop --reason done` —— 收租约，别挂着占位
2. 开一条 `[goal-achieved] P1` issue，**把判据命令的原始输出贴进去**（证据，不是结论）
3. 把本表 P2 的状态从 `needs-owner` 改成 `asked-owner`（提问后）
4. **停手**：不再从 `next` 领活。达标后自己找活干 = 偏离方向 + 烧 token

## agent 的权限边界

| 允许 | 禁止 |
|:--|:--|
| 给 owner 提 2–3 个候选下一阶段（带数据、推荐、代价） | 自己定下一阶段是什么（目标属方向，是 owner 的） |
| 把 P1 标达标、留下判据证据 | 达标后自己找活干「保持忙碌」 |

## 达标后提问模板（照这个格式问，不要开放式提问）

> P1 已达标（证据：`python3 scripts/nightly_gap.py` exit 0，见 issue #N）。
> 下一阶段候选：**A** … / **B** … / **C** …。
> 我推荐 A，理由：…；代价：…
> 你选哪个？
