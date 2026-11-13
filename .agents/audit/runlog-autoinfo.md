# Runlog — AutoInfo

基线 commit：`333a11c22d73e1361dd6f74a143f9375c785e5be`（2026-11-07，v1.28.2） | 分支：`ops/agent-infra` | 开始时间：2026-11-08
PR：https://github.com/1StepMore/AutoInfo/pull/724（**draft，未合并**，等 Owner 评审）

执行者：Ops-Executor（Owner 显式指派，非四角色）｜ 方针：02 稿 733 行 `5579f22a…`（QA 无条件 YES）｜ 拍板：Owner 2026-11-08 十项预授权

## 步骤记录

| 步骤 | 时间 | 结论 | 产出/证据 | 备注 |
|---|---|---|---|---|
| P0-S1 任务单 | 2026-11-08 | done | 五项齐备（目标指令「任务单五项」节） | 仅 AutoInfo；试点偏离备注=AutoInfo 非最小仓（Owner 决策 1） |
| P0-S2 env-check | 2026-11-08 | done | env-check.md | make 缺失→D8 备注；gh-aw 未装→按决策 7 D3 降级 |
| P0-S3 控制区初始化 | 2026-11-08 | done | 两份前置依赖已复制，哈希一致 | 日志放仓库外（P1/P2 只读） |
| P1-S1..S6 | 2026-11-08 | done | 基线锁定；20 子系统五维审计；敏感面（0 真实命中）；agent 设施清单；远端核对 | 全程只读，复查 git status=0 |
| P2-S1..S3 | 2026-11-08 | done | 双 inventory（LOCAL/REMOTE）+ 分类统计 + 自检 5 文件 | 分类：源码 505/测试 451/文档 169/CI 21/待废弃 0 |
| P3-S0..A14 | 2026-11-08 | done | 10 个动作 commit + 3 项 no-op 处置（A7/A11/A14）+ §5 期望层 commit | 明细见下表 |
| P4-S1 确定性校验 | 2026-11-08 | done（本地可得子集） | ruff 全量 PASS；mypy：4 错误均为 main 既有（干净 worktree 对照验证），A13 零新增，且 CI mypy 仅扫 src/；目标回归 tests/scripts+tests/gov：**526 passed / 3 failed（全部在干净 main worktree 复现=Windows 环境失败，非本分支引入）/ 8 skipped** | full pytest 快子集以 PR CI 为准（D8：本机无 make） |
| P4-S2 lock 权限复核 | 2026-11-08 | **SKIPPED-D3** | gh-aw 未装（决策 7），无 .lock.yml | 降级期间不宣称 gh-aw gate 生效 |
| P4-S3 四角色 dry-run | 2026-11-08 | **PASS 4/4** | 全新上下文子代理 ×4（显式点名）：角色/必读顺序/Done 逐条与契约一致 | 附加发现：未点名角色时正确输出 `ESCALATE`（禁自猜防线实测有效，02 稿 §0.1 设计验证） |
| P4-S4 E2E 基线校准 | 2026-11-08 → 2026-11-14 | **done（2026-11-14）** | #729 基线落地：E2E_CMD=`pytest tests/e2e/test_e2e_features.py -q`、E2E_RUNNER=验证场景引擎 `run_scenario`、首批 20 旅程挂场景 ID；Windows 校准 18 passed + 5 blocked-unconfigured（key/browser 前提缺失的引擎诚实读数） | GAP-01 解除；DEBT-03 关闭 |
| P4-S5 人工抽查清单 | 2026-11-08 | done（材料交 Owner） | 见 §8.4 签收清单 | 判定权在 Owner |
| P5-S1 归档入库 | 2026-11-08 | done | runlog + 双 inventory 入 `.agents/audit/`（commit `d0f86aaf` + 后续更新） | 控制区为权威原件 |
| P5-S3 控制区归档 | 2026-11-08 | done | 本目录即归档（agent-governance-autoinfo-20261108） | P5-S2 分支清理=Owner 合并后事项 |

## P3 动作清单（分支 ops/agent-infra，自基线 333a11c2）

| 动作 | commit | 自检 | 回滚 |
|---|---|---|---|
| A1 根 AGENTS.md 重构 | `0bc7dfe4` | 200 行=C3 顶棚 PASS（首提交 217 行自检不过，压缩后 amend）；零花括号占位符；invariant 表逐字保留 | `git revert 0bc7dfe4` |
| A10 目录级 AGENTS.md ×3 | `9b9e4945` | 11/10/9 行 ≤15；角色措辞一处修正后 amend；只描述地点 | `git revert 9b9e4945` |
| A2 四契约 + DEBT.md | `0c8b2708` | 28/27/29/25 行 ≤30；四要素齐；零占位符 | `git revert 0c8b2708` |
| ops(§5) 期望层 | `d49f1f9e` | 指针索引（决策 5）；EXP-AC..EXP-E2E 六行；CP-AGENTS..CP-E2E 八检查点 | `git revert d49f1f9e` |
| A13 一致性机制 | `6f6c5889` | C3/C4/C5/C7 实测 PASS；doc_inventory --check 含 C6 镜像 PASS（venv 解释器）；guard.yml 接线 required check | `git revert 6f6c5889` |
| A13 重生成（fix-then-gate） | `095403f3` | A8 新增 docs/user/README.md 后未重生成→**CI gate 真实抓到**（非注入）→同生成器重跑双镜像一致；同 commit 含 runlog 终版 | `git revert 095403f3` |
| A5 constitution 抽取 | `0b519b5b` | 零代拟、逐条出处；V08 诚实标注；供 Owner 事后审核 | `git revert 0b519b5b` |
| A3 .claude/agents/ ×4 | `02c965df` | frontmatter 齐；指针非复本；tester 只读 plan；R-2 标注 | `git revert 02c965df` |
| A4 .github/agents/ ×8 | `09cc06a3` | cloud .md ×4 + CLI/IDE .agent.md ×4（M4）；description 全在 | `git revert 09cc06a3` |
| A6 gh-aw 源 ×2 | `52710981` | D3 降级标注齐；.md 不被 Actions 执行；M1 draft 依据挂 gh-aw | `git revert 52710981` |
| A8+A9 骨架 | `7a6ec9f6` | 内容占位不代拟；GAP-01 显式声明 | `git revert 7a6ec9f6` |
| P5 归档 | `d0f86aaf` | runlog + 双 inventory 入库 | `git revert d0f86aaf` |

### no-op 处置（无 commit，非静默跳过）

| 动作 | 处置 | 依据 |
|---|---|---|
| A7 | ci.yml 已存在（BUILD/TEST/LINT 齐）不重写；一致性 gate 由 A13 接入 guard.yml required check | 目标指令 A7 口径 + 决策 4 |
| A11 | 跟踪文件 0 条满足三条件（LOCAL 报告）；疑似项均未跟踪运行产物，留 Owner 裁决 | P2 报告 |
| A14 | GAP-01/GAP-02 已登记 + tests/e2e README 声明，汇入 §8.4 | 决策 8 |

## Gate 记录

| Gate | 时间 | 结果 | 证据 |
|---|---|---|---|
| G0 | 2026-11-08 | PASS（带备注） | env-check.md |
| G1 | 2026-11-08 | PASS | 只读证明（git status 与基线一致） |
| G2 | 2026-11-08 | 材料产出（Owner 事后复核，决策 2） | inventory-local/-remote.md |
| G3 | 2026-11-08 | PASS | `git log main..ops/agent-infra` 与动作清单一一对应；每动作独立 commit+回滚；P3 diff 无业务逻辑改动（自查） |
| G4 | 2026-11-08 | 材料产出（Owner 事后复核，决策 2） | 本文件 CP-01..06 表 + §8.4 清单 + PR #724 |

## CP-01..06 状态表（02 稿 §8.2）

| CP | 检查点 | 状态 | 证据 |
|---|---|---|---|
| CP-01 | 根 AGENTS.md ≤200 行含 §0 安全+tiebreaker+路由+命令 | **PASS** | C3 实测 200 行；`0bc7dfe4` |
| CP-02 | 四契约四要素齐 ≤30 行、适配器指针非复本 | **PASS** | C4 实测 4/4；grep 指针存在 |
| CP-03 | 零占位符残留；INVENTORY.md AUTO-GENERATED 且与目录一致 | **PASS** | C5 实测（两次抓到真实残留并修复：checkpoints 自引用字面量、归档 runlog 描述性字面量）；C6 实测字节级一致 |
| CP-04 | 一致性 gate 生效：注入断链→CI 挡住 | **PASS** | 本地注入演练红（orphan 场景→C7 失败）+ **CI 真实抓到** A8 后的 inventory stale（PR #724 check 红→重生成修复） |
| CP-05 | gh aw compile --strict 全过；.lock.yml 权限最小 | **SKIPPED-D3** | gh-aw 未装（决策 7）；降级期间不宣称 gate 生效 |
| CP-06 | 20 用法小样本可跑；0% 覆盖显式登记 | **PASS（2026-11-14）** | 20 旅程全量可跑（E2E_CMD，Windows 实测 18 绿 + 5 blocked-unconfigured）；未覆盖的 169 场景显式登记于 `tests/e2e/features/README.md` 旅程表（0% 覆盖口径=仅首批 20 旅程挂接 35 场景） | 后续扩样由 Owner 增删旅程文件即自动生效 |

## 降级与遗留

| 编号 | 情形 | 处置 | Owner 确认 |
|---|---|---|---|
| 决策 7 | gh-aw 未装 | A6 落 .md 源标待编译；CP-05/§8.4 首条 SKIPPED-D3 | 已拍板 |
| 决策 6 | specify-cli 不装 | A5 只落单文件（抽取送审） | 已拍板 |
| D8 | Windows/Git Bash：无 make；3 个测试环境失败（main 上复现） | 直接命令替代 make；环境失败已用干净 main worktree 对照排除 | 无需（只读等效） |
| 本仓差异 | PR 标题 gate 白名单无 `ops` type | PR 标题用 `docs(agent-infra)`（scope 映射核实）；commit 内保留方针 `ops(A<N>)` 格式；squash 合并时 Owner 定夺最终标题 | 记录待 Owner 复核 |
| 遗留-1 | E2E 可执行基线（GAP-01） | PENDING-前置；DEBT-03 | Owner 待办 |
| 遗留-2 | ax_metrics/L1 battery 接线（GAP-02） | PENDING-前置；DEBT-01/02；属 10-30 计划范围 | Owner 待办 |
| 遗留-3 | ruleset 未加路径级 push rules（保护 .agents/expectations/） | 远端设置改动超出基础包预授权；等效约束=期望文件改动只能经 PR + 十项必过 | Owner 可选加固 |
| 遗留-4 | A13 新 gate 升级为独立 required check | 当前并入 derived_parity job 内生效；升级须改 ruleset（远端操作） | Owner 可选加固 |

## §8.4 Owner 签收清单（G4，不由执行者判定）

- [ ] 根 AGENTS.md §0 安全与 tiebreaker 符合预期；四契约四要素齐 ≤30 行（`0bc7dfe4`/`0c8b2708`）
- [ ] constitution 原则文本为 Owner 认可版本（`0b519b5b`，决策 6 送审承诺）
- [ ] 期望层指针索引方案（决策 5）认可；INDEX 版本锚策略认可
- [ ] 无多余写权限：gh-aw 源未编译无 .lock.yml（SKIPPED-D3）；仓库无密钥入库（pre-commit detect-secrets 全过；建议 Owner 合并前跑 GitHub secret scanning）
- [ ] 一致性校验 gate 实测挡 CI（CP-04：本地注入 + CI 真实抓取双证据）；Acid Test 三条：①仅凭 AGENTS.md 可 build/test（命令区齐）②INDEX 定位文档 ③stale 由 checker 挡
- [ ] 期望唯一事实源 + 改期望门禁（§0-4）生效认知一致
- [ ] SKIPPED/PENDING 项逐条签收：SKIPPED-D3（CP-05）；PENDING-前置（GAP-01/02、CP-06）
- [ ] 待废弃标记清单（0 条跟踪文件；8 处未跟踪运行产物清理与否）
- [ ] 本仓差异处置：PR 标题 `docs` type（squash 时可改）
- [ ] 试点校准记录：本 runlog 全文即试点校准输入（供方针修订用）
