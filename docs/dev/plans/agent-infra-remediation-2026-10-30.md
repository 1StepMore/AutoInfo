# 整改计划：Agent 基础设施有效性（2026-10-30）

> **来源审计**：`docs/agent-infrastructure-audit-2026-10-30.md`（27 项判定，4 🔶 名实不符 + 2 ❌ 闲置 + 9 🟡 部分有效）
> **状态**：⏸ 待 Director 批准——含 **3 个方向性决策点**（§决策点 A/B/C），P0 部分不依赖决策、可先行
> **执行体**：coding agent（tester 角色）　**批准人**：Director（B3）

---

## 0. 为什么先写 plan（对"要不要先写 plan"的回答）

**要。** 理由不是单项工作量大——恰恰相反，大部分整改是小时级的小改动——而是这条执行路径有四个只有 plan 能压住的东西：

1. **顺序依赖（fix-then-gate）**：把检查接进 CI 之前必须先知道它在本树是红是绿。接一个红的检查 = 把 main 顶红。例："147 tools" 清理必须与"把该文档纳入 LIVING_DOCS 核对"**同 PR**，且必须先于 CI 接线。
2. **3 个方向性决策必须由 Director 拍板**（D1-D3 默认行为、治理循环存废、operator skills 归宿）——这些是产品/流程决策，不是 agent 能自决的（符合 P5 "the agent grades; the human disposes"）。
3. **PR 批次策略**：本仓双写者 + release PR 自动合并，每次合并都要付 ~20 分钟 rebase 周期；AGENTS.md 的官方缓解是"更少、更大的 PR"。11 项整改若拆 11 个 PR 是自找麻烦，应合并为 **4 个 PR**。
4. **验收要可回放**：整改完成的判据 = 重跑审计的 27 项判定表，🔶/❌ 归零。没有 plan 就没有这张对照表。

## 1. 总原则

- **fix-then-gate**：先修漂移、后上门禁。任何新 CI 检查合入前的上一个 PR 必须已让它在本树变绿。
- **起步不阻塞**：有历史噪音的检查（L0 的 D2 orphan ~27% 误报、ax_metrics 依赖已断流的 9 月数据）先以 report-only / continue-on-error 接入，观察期后再转阻塞。
- **名实归一优先于功能新增**：本计划不新增任何能力，只把"已声明的能力"变成真的、或把声明改诚实。
- **遵循仓库既有纪律**：squash merge、rebase onto origin/main、PR 模板的回归场景声明、AGENTS.md ≤452 行（AC8 基线，当前 402，余量 50 行）。

---

## 2. Wave 0 — 基线（无 PR，半天）

| 步骤 | 内容 | 产出 |
|---|---|---|
| 0.0 | ~~建 venv~~ → **更正（2026-10-30，Director 指正）**：项目已有 venv，在 WSL 侧（`.venv/bin/python`，Python 3.14.4，主力 agent 环境）；Windows 侧不另建。基线统一经 `wsl -e bash -c "cd /mnt/d/贯维/AutoInfo && .venv/bin/python …"` 执行——且 CI 本就是 Linux，WSL 基线比 Windows 原生更接近 CI 环境 | 复用现有环境 |
| 0.1 | 本地跑五件仪器并记录红绿：`doc_inventory.py --check`、`surface_parity.py --check`、`coverage_matrix.py --check-enduser-doc`、`ax_metrics.py`、L0 `quality_gate.py`（对 outputs/ 有产物的域） | 基线记录（见下方执行记录） |
| 0.2 | 对红灯项逐个定性：真漂移 → 进 Wave 1 修复清单；仪器自身问题 → 进该仪器的处置项 | Wave 1 增补项 |

### Wave 0 执行记录（2026-10-30，WSL venv 实测）

| 仪器 | 结果 | 定性 |
|---|---|---|
| `doc_inventory.py --check` | **FAIL ×1**：`docs/dev/doc-inventory.md` 不是最新（本 plan 与审计报告两份新文档未重新生成 inventory）。**其余全绿**：149 工具 / 35 类 / 31 CLI / 182 场景 / 6665 测试 / 9 份 living docs 全部 match | 唯一红灯 = 我自己新增文档引出的预期漂移；修复 = Wave 1 重新生成 inventory（本就列入 PR-1）。另确认：acceptance-framework 虽在 living-doc 核对内且 "counts match"，但 "147/147" 仍存活——核对逻辑是"当前计数存在即可"，挡不住陈旧数字，Wave 1 的 1.3/1.4 清理照做 |
| `surface_parity.py --check` | **PASS**（0 unaccounted endpoints，canonical 8/8） | 可直接接 CI |
| `coverage_matrix.py --check-enduser-doc` | **PASS**（99 项矩阵与 spec 渲染逐字节一致） | 可直接接 CI |
| `ax_metrics.py` | **5/6 PASS，M-04 FAIL**——根因同上（stale inventory）。M-01/02/03/06 全部取到"活数据"但样本来自 2026-09-13 的旧 run，证实"仪器可跑、数据源断流"的审计判断 | report-only 接线可行；门槛化依赖决策点 B 恢复数据源 |
| L0 `quality_gate.py` | medical-research：55 defects / 52 files（全部为 2026-08 历史产物的 H3 粘连/C4 截断/H2 词边界类——残差登记在案的已知良性类）；language-learning：1 defect（同类）；ai-commercial：无 .md（usage error，产物在别处） | **修正 Wave 2 方案**：L0 若对整个 `outputs/` 树跑，历史噪音立刻 56 条——nightly 接线必须**只扫当次 run 新鲜产物**（按时间过滤或扫描指定 run 目录），不是全树 |

**Wave 0 结论**：仪器层健康——四件可直接进 CI/nightly（一件需先重新生成 inventory）；唯一红灯的根因是本计划的伴生漂移，已定性、已列修。fix-then-gate 前提成立。

### Wave 0 补充：全新 checkout 模拟（执行前审查，2026-10-30）

用 `git worktree @HEAD`（无 `outputs/`、无 `validation-runs/`、无 db）模拟 CI 环境：

| 仪器 | 结果 | 对 Wave 2 的影响 |
|---|---|---|
| `doc_inventory --check` | PASS（HEAD 上 inventory 本就新鲜；红灯只存在于含未提交新文档的工作区） | 可直接上 CI |
| `surface_parity --check` | PASS | 可直接上 CI |
| `coverage_matrix --check-enduser-doc` | PASS——**确认不依赖 `outputs/`** | 可直接上 CI |
| `ax_metrics` | **GATE PASSED, exit 0**——脚本本就为全新 checkout 设计：`UNMEASURED` 永不炸门禁；M-04/M-05 可测（token baseline 是 committed 文件）；run 侧指标随数据出现自动激活 | **升级 Wave 2.3：直接进 nightly 当真门禁，无需 report-only 降级** |

**注**：审查期间 HEAD 已由 release bot 前移至 1.21.5（`31c93323`）；本表与全部编辑点已在 1.21.5 复核仍成立。

**红线**：Wave 0 发现的漂移修复不完，Wave 2 的 CI 接线就不开工。

---

## 3. Wave 1 — 文档与名实归一（PR-1，纯文档/注释/Makefile，无行为变更）

| # | 改动 | 文件 | 备注 |
|---|---|---|---|
| 1.1 | 门禁表给 G4/G5/D1-D3 加真实默认标注（"opt-in via `--check-factual` / `delivery_gates` 配置；demo 默认未启用"）；Quick Start 的 `# quality gates` 注释同步 | `AGENTS.md` | 行数预算 ≤452，当前 402 |
| 1.2 | §5.1 "Hard gates cannot be bypassed" 补执行时语义（hard = 执行时不可绕过；G4/G5 在 process 层为 opt-in，G4 默认唯一执行点是晋升 CurationGate） | `docs/dev/acceptance-framework.md` | 框架级措辞变更，按 §7.6 属 routine evidence 修订，记录于本 plan 即可 |
| 1.3 | "147" 残留清理（:51/:219/:248 → 149 或改为对 README Status 的引用） | `docs/dev/specs/user-lifecycle-definition.md` | |
| 1.4 | "147/147" 清理（§3.1 判据 1 + 附录 A1 行） | `docs/dev/acceptance-framework.md` | |
| 1.5 | frequency_gate docstring 与现实对齐（删去不存在的 MCP 路径，注明唯一调用点 CLI cron；是否补 MCP 接线另立 issue，见决策点 A 附带项） | `src/autoinfo/delivery/frequency_gate.py` | 仅 docstring |
| 1.6 | ~~ax_metrics docstring~~ **移至 Wave 2.3**（与 nightly 接线同批落地，避免"声称已接线而实际未接"的窗口期） | — | 见 2.3 |
| 1.7 | `user-lifecycle-definition.md` 纳入 LIVING_DOCS 数字核对。**审查修正**：acceptance-framework 本就在清单内——其 "147/147" 漏网是因为核对正则只匹配「数字+单位」语序（"147 tools"），匹配不了 "tools (147/147)" 这种单位在前的写法；正则语序加强 → P2 待办。核对单测（`test_doc_inventory_living_docs.py`）钉的是匹配行为而非清单内容，无需改测试 | `scripts/doc_inventory.py` | **必须与 1.3 同 PR**（该文档现含 "147 tools"，纳入即被命中） |
| 1.8 | ✅ 已修（2026-10-30）：删除 `skills/` 忽略行。**执行更正**：`.opencode/.gitignore` 实为**从未被 git 跟踪的本地文件**（审计的"已跟踪但被忽略"表述有误）——修复仅存在于本机工作区，无可提交物 | `.opencode/.gitignore`（本地） | 本机陷阱已消除 |
| 1.9 | Makefile 加 `battery` target（默认预览模式，`SEMANTIC=1` 透传 `--semantic`）；`validate` 的 echo 提示同步指向 `make battery` | `Makefile` | L1 拿到第一个扳机点 |
| 1.10 | 重新生成 `docs/dev/doc-inventory.md`（收录审计报告与本计划两份新文档——Wave 0 唯一红灯的修复） | `docs/dev/doc-inventory.md` | 生成物，跑 `scripts/doc_inventory.py`（无 --check） |

**验证**：`make doc-check` 绿；`grep -rn "147" docs/dev/specs/user-lifecycle-definition.md docs/dev/acceptance-framework.md` = 0；`wc -l AGENTS.md` ≤452；`pytest tests/scripts tests/doc_inventory* -q` 绿。

---

## 4. Wave 2 — CI 接线（PR-2，改 2 个 workflow）

| # | 改动 | 文件 | 起步强度 |
|---|---|---|---|
| 2.1 | guard.yml 新增 `derived-facts` job（与既有 grep-assert 并列，pull_request + push main 均触发）：`pip install -e ".[dev]"` 后依次跑 `doc_inventory.py --check` + `surface_parity.py --check` + `coverage_matrix.py --check-enduser-doc` | `.github/workflows/guard.yml` | **阻塞**——三者在全新 checkout worktree 模拟中全部 PASS（不依赖 `outputs/`），可直接上 |
| 2.2 | **撤销原方案**（nightly 跑 L0）：CI 是全新 checkout、无任何产物可扫，L0 进 CI 是假接线。处置：L0 维持 `make validate` 手动 + demo-release DoD 程序性强制 + pytest 单测覆盖逻辑（已在 CI）；**后续候选 issue**：把 L0 接入 `validation_delivery.py` 打包流程（产物真实产生之处） | — | 诚实处置优于假接线 |
| 2.3 | nightly 追加 `ax_metrics.py` 步骤（全量 install 之后）：M-04（文档新鲜度）+ M-05（token 基线，keyless、baseline 已提交）在 CI 真实门禁；M-01/02/03/06 无 runs 数据时报 UNMEASURED（不炸门禁），决策点 B1 落地后自动激活。随本项同步修 ax docstring（自 1.6 移入） | `.github/workflows/nightly.yml`、`scripts/ax_metrics.py` | **真门禁**（worktree 实测 exit 0、UNMEASURED 语义已验证） |

**验证**：PR 上三个 --check job 绿；nightly 手动触发一次，artifact 里有 L0 报告与 ax 报告。
**回滚**：均为纯 workflow 改动，revert 即回滚。

---

## 5. Wave 3 — 决策驱动项（各一个 PR，前置 = Director 拍板）

### 决策点 A：G4/G5 与 D1-D3 的默认行为（🔶-1/🔶-2 的终态）

| 选项 | 内容 | 代价 | 建议 |
|---|---|---|---|
| **A1 文档诚实化（推荐）** | Wave 1 的 1.1/1.2 即为终态；另把审计 §4 的"真实默认行为表"正规化进 `docs/dev/specs/quality-gates.md` 新增一节"默认行为矩阵" | 零运行成本 | ✅ opt-in 大概率是成本设计（LLM 判定按 item 计费），诚实标注即可 |
| A2 配置默认化 | 把 D1-D3 阈值写进 `default_config.yaml`（有记录的默认），AGENTS.md 表述随之成真；G4/G5 维持 opt-in | 需先 spike：确认 D1-D3 在无 LLM key 时是否可运行、每次交付的成本画像 | 若 spike 显示确定性/近零成本，A2 优于 A1 |

附带小决策：**frequency_gate 是否真补 MCP `add_delivery_schedule` 接线**（小 feature + 回归场景）——建议单独立 issue，不塞进本计划。

### 决策点 B：验证治理循环存废（❌-16 的终态）

| 选项 | 内容 | 建议 |
|---|---|---|
| **B1 轻量重启（推荐）** | (i) nightly 加一步 keyless 子集 suite run 并**持久化到 validation-runs/ + sessions/**（CI 每周已经在跑同一子集，只差持久化——同时喂活 ax_metrics M-01/02/03 的数据源）；(ii) loop-log 更新并入 `demo-release-standard.md` 的 DoD checkbox；(iii) 完整 182 场景 suite 维持按需手动（有 key 的 release 前跑） | 复用已有 CI 资产，边际成本低；让"循环"重新有数据流 |
| B2 正式降级 | 修订 `validation-governance.md`：循环改为按需触发，归档 2026-08 版契约承诺，loop-log 冻结并标注 | 若 Director 判断循环型验证不再符合当前阶段的工作方式 |

### 决策点 C：operator skills 归宿（❌-24 的终态）

| 选项 | 内容 | 建议 |
|---|---|---|
| **C1 升入可发现路径（推荐）** | 两份 SKILL.md 补 frontmatter，移入 `.opencode/skills/autoinfo-operator/`；AGENTS.md 目录树同步；doc_inventory 的 LIVING_DOCS 路径引用**同 PR 更新**（它按路径核对 autoinfo-skill/SKILL.md） | 成本一个 PR，agent-as-user 从此真能发现它们 |
| C2 降级为参考文档 | 原地保留，AGENTS.md 标注改为"参考文档（非 skill）"，从 "skills" 话语体系中摘出 | 若判断 operator 指引应由 AGENTS.md/工具描述承载，文档就该叫文档 |

---

## 6. Wave 4 — P2 清尾（可并入 PR-1 或单开小 PR）

- `scripts/` 全量注册表：gate / instrument / one-off + 接线状态。**倾向生成式**（扩展 doc_inventory 输出，符合 AC8 判据 3 "generated, not hand-maintained"），目标产物 `docs/dev/infra-registry.md`（AUTO-GENERATED）。

---

## 7. 决策点汇总（给 Director 的一页纸）

> **裁决记录（2026-10-30，Director）**：A → **A1**（维持 opt-in；Wave 1 的文档诚实化即终态）。B → **B1**（已执行：`scripts/nightly_validation_run.py` 持久化 runner + nightly 步骤 + demo-release-standard DoD"验证循环闭环"项）。C → **C1**（已执行：两 skill 移入 `.opencode/skills/`、autoinfo-skill 补 frontmatter v1.1.0、7 处路径引用同步；保留原目录名以最小化引用变更）。A′ 已随 Wave 2.3 落地（ax_metrics 进 nightly 真门禁）。**Wave 3 全部落地。**

| 决策点 | 问题 | 推荐 | 不推荐的维持现状原因 |
|---|---|---|---|
| A | G4/G5/D1-D3 默认行为：文档改诚实（A1）还是配置给默认（A2）？ | A1（若 spike 显示 D1-D3 近零成本则 A2） | 维持现状 = agent 按 AGENTS.md 行事会高估默认质量防线 |
| B | 验证治理循环：轻量重启（B1）还是正式降级（B2）？ | B1 | 维持现状 = 契约有效但无人履行，后来者无法区分静默债务与设计如此 |
| C | operator skills：升入可发现路径（C1）还是降级为参考文档（C2）？ | C1 | 维持现状 = 文档孤岛，agent-as-user 永远发现不了 |
| A′ | ax_metrics：接线（随 B1 数据源恢复后门槛化）还是永久手动？ | 随 B1 走，先 report-only | 维持现状 = docstring 已在撒谎（Wave 1 先改口） |

**可以立即批准的**：Wave 0 + Wave 1 + Wave 2（不依赖任何决策点；A1 的文档措辞本身也是 A 决策的 A1 选项实现，若 Director 选 A2 只需追加配置 PR）。

---

## 8. 验收标准（整改完成的定义）

1. 重跑审计 27 项判定表：**4 个 🔶 全部归零**；2 个 ❌ 按决策点处置后转为 ✅ 或"有记录的降级"；🟡 中 17/18/19/20（仪器未接线类）转 ✅。
2. 四件仪器（doc_inventory / surface_parity / coverage_matrix --check / ax_metrics）在 CI 或 nightly 有真实门禁；L0 维持手动 + 单测，并立候选 issue（接入 validation_delivery 打包流程）。
3. `grep` 复查审计 §3.2 的名实不符清单 = 零命中。
4. CI 全绿；`wc -l AGENTS.md` ≤452；`make doc-check` 绿。

## 9. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 接线把既有漂移顶成红灯 | Wave 0 基线 + fix-then-gate 顺序 |
| L0 无法进 CI（全新 checkout 无产物可扫） | 已按 Wave 2.2 撤销假接线；维持手动 + DoD + 单测；候选 issue 转打包流程 |
| PR 撞上 release auto-merge 的 rebase 周期 | 合并为 3-4 个 PR；按 AGENTS.md 预算每次 ~20 分钟 CI 周期 |
| 移动 skills 路径破坏 doc_inventory 按路径核对 | 路径变更与 LIVING_DOCS 更新强制同 PR |
| 本机 Windows 与 CI Linux 差异 | Wave 0 已用 worktree 在 Linux（WSL）实测四仪器全 PASS；nightly 首跑人工确认 |

## 10. PR 划分与预算

| PR | 内容 | 预估体量 |
|---|---|---|
| PR-1 | Wave 1 全部（文档归一 + docstring + gitignore + Makefile + LIVING_DOCS 扩容 + inventory 重生成） | ~8 文件，低风险 |
| PR-2 | Wave 2（guard.yml 新 job + nightly ax 步骤 + ax docstring） | ~3 文件 |
| PR-3 | Wave 3（B1：持久化 runner + nightly 步骤 + DoD 项；C1：skill 迁移 + 7 处引用同步） | ~14 文件（含 2 个 git rename） |

> **执行注（2026-10-30）**：PR-1/2/3 有文件重叠（nightly.yml、AGENTS.md），且已全部在同一工作树验证为绿——建议合并为**单个 PR** 提交（符合 AGENTS.md "更少、更大的 PR" 缓解纪律）。
| PR-4 | Wave 4 注册表 + 本 plan 的基线附录回填 | 1-2 文件 |

每个 PR 按模板声明回归场景（文档类 PR 声明 `make doc-check` + 相关 pytest 子集即可）。
