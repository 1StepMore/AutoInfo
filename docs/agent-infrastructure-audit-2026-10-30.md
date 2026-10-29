# AutoInfo Agent 基础设施有效性审计（2026-10-30）

**日期**：2026-10-30（HEAD `96f7fefe`，v1.21.4）
**范围**：为两个 agent 角色服务的全部基础设施——skills 文档、质量门禁（G0-G7 / D1-D3 / L0 / L1）、hooks 与 CI 强制层、验证场景体系、防漂移机器、AX 度量、agent 接入配置。
**方法**：三路并行调查（gates 接线 / 验证场景体系 / skills·hooks·配置）+ 核心设计文档精读（founder-expectations、user-lifecycle-definition、acceptance-framework、autoinfo-skill）+ 对关键声明逐条实测（每个判级都附代码或产物证据，复现命令见文末）。
**与既有报告的关系**：`docs/project-analysis-2026-10-29.md` 管产能与代码缺陷（832 格、KB 空层、cost.py 缺陷等）；本报告不重复其结论，只回答一个问题——**这套为 agent 建的基础设施，哪些真的在起作用，哪些是纸面的**。

---

## 1. 分析框架

### 1.1 前提：两个 agent 角色

前提出自仓库自己的成文定义（`docs/dev/acceptance-framework.md` §0.2）：B2 Direct User 是 "the AI agent that operates the platform. **Agent as user and agent as tester**"。两个角色的基础设施需求不同：

| 角色 | 是什么 | 基础设施要回答的问题 |
|---|---|---|
| **Agent as user（B2）** | 通过 MCP/CLI 操作 AutoInfo 产品管线、服务 B1/B3 的 agent | agent 能发现能力吗？能被约束吗？产物机器可读吗？它读到的"质量防线"是真的吗？ |
| **Agent as tester** | 开发并验证 AutoInfo 本身的 coding agent | 验证能在真面上执行吗？会被强制吗？证据有人消费吗？循环闭合吗？ |

### 1.2 有效性判据（5 条）

1. **可达性**：agent 能通过真实通道发现它（协议发现 / AGENTS.md 自动加载 / mcp.json / 标准技能路径），还是只有"记得它存在的人"能用。
2. **真实执行**：在真实表面上执行（无 mock），缺依赖时报 `unconfigured` 而非假通过。
3. **接线等级**：CI 强制 > 代码默认执行 > 代码 opt-in（旗标/配置）> Makefile·手动 > 纯文档。等级本身不是罪——问题是**声明的等级与实际的等级是否一致**。
4. **名实一致**：文档、docstring、门禁表向 agent 承诺的强制等级必须等于实际接线等级。**名实不符单独判级**：对一个 agent-first 项目，这类失真比普通项目更危险，因为 agent 按文档行动、没有"常识"兜底。
5. **闭环**：产物有人消费——报告被读、台账被更新、门禁失败会回流到修复。

### 1.3 判级符号

✅ 有效　🟡 部分有效（机制真实但覆盖不全 / 依赖手动 / opt-in 无触发器）　🔶 名实不符　❌ 无效或闲置

---

## 2. 总览判定表

| # | 基础设施 | 服务对象 | 接线现状 | 判级 |
|---|---|---|---|---|
| 1 | MCP 面（149 工具 + `{success, error:{code,message,actionable}}` 统一 envelope） | user | 代码默认执行；场景+单测钉住 | ✅ |
| 2 | 三份开箱 MCP 配置（.opencode / .cursor / .claude） | user | 已提交，5 秒接入属实 | ✅ |
| 3 | KB 管线纪律（01-Raw 唯一入口 / agent 晋升 / Wiki 只增不删） | user | **代码强制**（CurationGate、WIKI_PROTECTED）+ 场景锁定 | ✅ |
| 4 | 诚实工程机制（unconfigured≠pass、honest hedge=PASS、TRIAGE 身份锁） | 双方 | 多层执行 | ✅ |
| 5 | AGENTS.md（402 行索引式 agent 手册） | user | 仅 OpenCode 自动加载；Cursor/Claude 不注入 | 🟡 |
| 6 | process 层 G0/G1/G1-ToS/G2/G3/G7 | user | 代码默认执行 | ✅ |
| 7 | G4 事实一致 / G5 翻译门禁 | user | **默认关闭**（CLI 旗标 + MCP 参数均 False）；仅晋升路径默认跑 G4 | 🔶 |
| 8 | D1-D3 交付门禁 | user | **默认从不触发**（全仓 0 处 `delivery_gates` 配置） | 🔶 |
| 9 | `delivery/frequency_gate.py` | user | 仅 CLI `cron add-delivery` 调用；docstring 声称的 MCP 路径不存在 | 🔶 |
| 10 | L0 `scripts/quality_gate.py`（F1-F4/C1-C6/G6/H1-H3/X1） | tester | 单测在 CI；**本体仅 `make validate` 手动**，是 demo-release DoD 的程序性 checkbox | 🟡 |
| 11 | L1 `scripts/agent_review/battery.py` + blindspots.yaml（20 条盲点） | tester | 零接线（连 Makefile target 都没有，仅 echo 提示）；设计本身（PASS/FLAG/ESCALATE、fail-loud）精良 | 🟡 |
| 12 | `delivery/gate_report.py`（01-QA-GATES md+json 双格式） | user | mvp CLI 与 validation_delivery 两路径默认执行 | ✅ |
| 13 | 验证场景引擎 + 182 场景（三态判定/恢复步骤/部分通过/超时） | tester | 代码默认；230+ 单测进 CI | ✅ |
| 14 | CI 场景强制（全库解析 + keyless 子集真实 dispatch，`scenario_portability_gate`） | tester | **CI 硬接线**（ci.yml:298） | ✅ |
| 15 | MCP 自助测试工具（list/run/run_all/get_run_decisions） | tester | 代码默认 | ✅ |
| 16 | 验证治理循环（validation-governance 契约 + loop-log） | tester | **2026-09-13/14 后熄火**；契约无机械触发器 | ❌（当前闲置） |
| 17 | `scripts/doc_inventory.py --check`（7 项防漂移，含工具表双向核对） | tester | **未进 CI**；仅 `make doc-check` 手动 | 🟡（仪器最强，接线最弱） |
| 18 | guard.yml Drift Guard（禁字符串块名单） | tester | CI 强制，但块名单只能挡已知漂移 | 🟡 |
| 19 | AX 度量 `scripts/ax_metrics.py`（M-01..M-06） | user | docstring 声称 "targets that CI enforces"；**CI/Makefile 0 接线** | 🔶 |
| 20 | `scripts/surface_parity.py --check`（REST 全路由对账） | tester | 未进 CI，手动 | 🟡 |
| 21 | coverage_matrix + enduser 矩阵 `--check-enduser-doc` | tester | 未进 CI；重生成靠 AC4 prose 职责 | 🟡 |
| 22 | AC1-AC9 验收框架（二元判据 + A1-A24 证据目录） | tester | 章程成色高；触发纯靠 prose；最近验收报告 2026-09-29 | 🟡 |
| 23 | `.opencode/skills/` 4 个开发者技能 | tester | OpenCode 标准路径自动发现 | ✅（限 OpenCode） |
| 24 | `docs/skills/` 2 个 operator 技能 | user | 无 frontmatter、非标准路径、无加载器——**文档孤岛** | ❌（作为 skill）/ 🟡（作为参考文档） |
| 25 | hooks：pre-commit（ruff/gitleaks/no-credential-url）+ 8 条 workflow | tester | 本地 + CI 双层在位 | ✅（缺口见 §7） |
| 26 | release 机器（release-please + 自动合并 + manifest 对账） | tester | CI 全自动闭环 | ✅ |
| 27 | `scripts/` 其余 30+ 审计脚本长尾 | tester | 可重跑证据机器；Makefile 仅暴露 2 个；无 gate/instrument 注册表 | 🟡 |

---

## 3. Agent-as-user 面：运行时名副其实，质量防线图景部分是纸面的

### 3.1 有效的部分

**MCP 面本身是全仓最扎实的 agent 基础设施。** 149 个工具、统一 envelope、`actionable` 错误提示、`LLM_NOT_CONFIGURED` 语义、`{status:"noop"}` 而非报错——这套约定在 `mcp/errors.py`（29 个错误码）和 dispatch 表（#581 重构后的 `server.py` hub）中被一致执行，且有 182 个场景 + 数百个单测钉住。AC1 判据 1（"agent 仅凭 MCP 面可操作全生命周期"）在设计上是满足的。

**三份开箱配置真实有效**：`.opencode/mcp.json`、`.cursor/mcp.json`、`.claude/claude_desktop_config.json` 都指向 `python -m autoinfo.mcp.server` 并透传 `AUTOINFO_LLM_API_KEY`——"5 秒接入"的承诺属实。

**KB 管线纪律是"纸面规则 → 代码强制"的范本。** 01-Raw 唯一入口、agent 无闸晋升（`promotion.py` 的 CurationGate：溯源 + G0 + G1≥30 + G3≥30 + G4 复核）、03-Wiki 只增不删（`WIKI_PROTECTED` 挡非 director 删除）都在代码层强制，`director-backdoor.yaml` 场景锁行为。这是全仓其他"约束"应当看齐的强制等级。

**诚实工程机制多层在位**：场景缺 key 报 `unconfigured`（`validation.py` 的 `_unconfigured_scenario_result`，整场景不执行、逐 step 标注、写明 Director 该做什么）；TRIAGE 按测试 ID 锁定身份；残差登记表"登记在先修复在后"；L1 battery 把"诚实的不确定"判为 PASS。这套机制在本轮核实中确认真实被执行（预算清零、P0 清偿有证据链——见 10-29 报告 §五）。

### 3.2 名实不符的部分（对 agent 最危险的一类）

**🔶 发现一：G4/G5 按"管线门禁"表述，实际默认关闭。**
- 实际接线：`src/autoinfo/cli/process.py:41-50` 的 `--check-factual` / `--check-translation` 旗标；MCP `process_collection` 参数 `check_factual`/`check_translation` **schema default False**（`src/autoinfo/mcp/tools/sources.py:578-594`）；`process.py:927` 签名默认 False。即所有采集处理路径上，这两个门禁**默认一次都不跑**。唯一默认跑 G4 的地方是 Draft→Wiki 晋升的 CurationGate（`promotion.py:199,217,264`）——而 10-29 报告实测 02-Draft/03-Wiki 为 0 条，**即 G4 默认执行的那个路径至今从未发生过**。
- 声明侧：AGENTS.md Quick Start 写 `autoinfo process --domain medical-research  # LLM extraction + quality gates`；AGENTS.md 门禁表把 G4 列为 "🔴 Hard … 3× retry with escalating context → block"（全文无一处提到 opt-in，grep `check_factual` 于 AGENTS.md 0 命中）；Collection Pipeline 一节写 "Phase 2 — Process: … → Quality gates (G1-G5)"；acceptance-framework §5.1 判据 1 写 "Hard gates cannot be bypassed. … G4 … 3× retry with escalating context, then block"。
- 判定：门禁**实现**是硬的（跑起来时不可绕过、retry-then-block、`_failed/` 落盘——这些都真实），但**门禁本身是 opt-in 的**这一事实没有进入任何 agent 面文档。一个按 AGENTS.md 行事的 agent 会高估 process 阶段的默认质量防线。opt-in 大概率是成本设计（LLM 判定按 item 计费）——合理，但合理的设计选择必须写进 agent 手册。

**🔶 发现二：D1-D3 交付门禁默认从不触发。**
- 实际接线：`output/gates.py` 的 `_resolve_delivery_gates`（:29）从项目 config 的 domain/global `delivery_gates` 解析，**无配置则直接返回 None、整个交付门禁层跳过**（:331-336）。实测 `src/autoinfo/data/default_config.yaml` 与 `data/domains/*`（21 个域配置）中 `delivery_gates` **0 命中**；MCP 路径（`mcp/context.py:742`）从不显式传入。即：AGENTS.md 表中 "D1: Product completeness 🔴 Hard 🔴 P0 → Blocks delivery" 在**当前默认部署下的所有生成路径（含 MCP generate_digest/report）上从未执行过**。
- 对照：AGENTS.md 写 "D1-D3 check product completeness, format integrity, and freshness **at output time**"，未提配置 opt-in。

**🔶 发现三：`frequency_gate.py` docstring 与代码不符。** 模块 docstring 声称 MCP `add_delivery_schedule` 也走频控；实测 `src/autoinfo/mcp/tools/scheduling.py` 对它 **0 引用**，唯一生产调用点是 CLI `cron add-delivery`（`cli/cron.py:1100-1102`）。读 docstring 的 agent 会以为 MCP 加交付计划也受频控——实际不受。

**🔶 发现四：AX 度量自称 CI 强制，实际无人执行。** `scripts/ax_metrics.py` docstring 明写 "each with a target that **CI enforces**"（M-01 任务完成率 >95% … M-06 错误恢复 <30s），但 `.github/workflows/`（8 条）与 Makefile 对 `ax_metrics` **0 引用**，仅 `tests/scripts/test_ax_metrics.py` 测了度量逻辑本身。对一个 agent-first 项目，AX 度量是正确且稀缺的想法（把 agent 的使用体验钉成指标），但它目前是一件没有扳机的武器。

### 3.3 部分有效的部分

**🟡 AGENTS.md 是枢纽但只有一条自动加载通道。** OpenCode 按约定加载根目录 AGENTS.md；`.cursor/` 只有 mcp.json（无 rules）、`.claude/` 只有 Desktop MCP 配置、仓库无 CLAUDE.md——Cursor 和 Claude 侧的 agent 不会自动注入任何仓库规则，只能靠主动读文件。402 行、索引式、pointer-only（计数指向 README）、被 guard.yml 扫描——内容治理是好的，分发是单点的。

**🟡 Agent constraints（MUST NOT 表）强制层级混杂。** 有的已代码化（Wiki 删除被 WIKI_PROTECTED 挡、`configure_llm` 只存 `${ENV}` 引用），有的纯 prose（"Do not run autoinfo doctor"）。CLI 作为人类降级通道保留这些能力是设计使然，但 agent 侧的约束目前一半靠代码、一半靠"agent 读过且遵守手册"。

---

## 4. 质量门禁（生产 QC）：实现被 CI 钉住，执行靠纪律

一张表说清 process/output 各门禁的**真实默认行为**（这是 agent 手册应当写而没写的表）：

| Gate | 代码位置 | 何时真的跑 | AGENTS.md 的表述 |
|---|---|---|---|
| G0 Schema | quality.py:321 | process 默认（block 无重试，写 `_failed/`）；晋升复核默认 | ✅ 一致 |
| G1 / G1-ToS / G2 / G3 | :431/:530/:688/:867 | process 默认（soft，按配置 archive/flag/pass） | ✅ 一致 |
| G4 事实一致 | :1297 | **process 默认不跑**；晋升复核默认跑 | 🔶 未提 opt-in |
| G5 翻译 | :1617 | **默认不跑** | 🔶 未提 opt-in |
| G7 实体一致 | :2027 | process 默认（flag-only，配置可升 block） | ✅ 一致 |
| D1/D2/D3 | :2132/:2446/:2979 | **默认从不跑**（无任何默认配置） | 🔶 未提 opt-in |
| G6（汇率越界） | **不在 quality.py** | L0 脚本检查项之一 | 🟡 编号归属易误导（#657 已修 glossary） |

**L0（`scripts/quality_gate.py`，1506 行）——工具有效，接线手动。** 检查项完备：F1 空壳 / F2 占位符 / F3 重复引用 / F4 域禁词 / C1 合成条目 / C2 日志泄漏 / C3 CJK 残留 / C4 截断 / C5 引用完整性 / C6 叙事孤儿断言 / G6 汇率 / H1 叙事信号 / H2 词边界截断 / H3 bullet 粘连 / X1 跨产品实体冲突；exit 0/1/2 语义清晰；有专门单测（`tests/scripts/test_quality_gate.py`）。但唯一执行入口是 `make validate DIR=…`，8 条 workflow 0 引用。它的强制形态是 `docs/demo-release-standard.md` 里的一行 DoD checkbox（"L0 gate: 无真实缺陷"）——**程序性强制**（靠 agent/人记得勾），不是机械强制。

**L1（`scripts/agent_review/battery.py` + `blindspots.yaml`）——设计精良，零扳机。** PASS/FLAG/ESCALATE 三判定 + 不可达/不可解析一律 ESCALATE 绝不 PASS（fail-loud 契约 :504-509）+ `--semantic` 走配置化 LLM 通道（vendor 无关，#194/#195）+ 20 条语义盲点（10 family：覆盖缺失、断言编造 vs 诚实含糊、推理措辞、价值层级……）。它**按设计就是 opt-in**（issue #194 的 L0/L1/ESCALATE 分层），但现状连 Makefile target 都没有——`make validate` 后只 echo 一句提示命令。分层设计的本意是"L1 是可选加深"，结果是 L1 只在有人记得时才存在。

**gate_report（`delivery/gate_report.py`）——双取向设计的范例。** 同一份门禁结果出 md（给人）+ json（给 agent）到 `01-QA-GATES/`，并诚实声明 "G0-G5 于 process 层执行"（:486-492）；在 `mvp` CLI 与 validation_delivery 两条路径上默认执行。这是"agent-operated tool、human-first results"（AC3 双取向）在基础设施上的正确样子。

**区分两件事**：门禁**实现**有 CI 覆盖（`tests/quality/`、`tests/llm/`、`tests/delivery/`、`tests/output/` 等数十个文件随 `pytest -m "not real_api"` 每次 PR 全跑）——这是"✅"；门禁**对产物的执行**不在任何 CI 里——这是"🟡/🔶"。CI 验证的是"门禁逻辑对"，从不验证"门禁跑了"。

---

## 5. 验证场景体系：机器层是同类项目少见的完备，治理循环已熄火

### 5.1 有效的部分（引擎层 ✅）

- **182 个场景**（86 functional + 96 regression），5 类 category × 4 层 pyramid × 18 级生命周期坐标（A1-A7 × B1.1-B3.5）。96 个回归场景按 issue 编号、强制 `regression_issue` 字段——bug→场景机器可审计（TR-S-05）。
- **引擎无 mock**：mcp step 走真实 `server.call_tool` dispatch；cli step 真实子进程（独立进程组、超时 SIGKILL 全组）；http step 真实 httpx。逐 step `asyncio.wait_for` 超时 + 协作取消 + `recovery_steps`（主 step 保持 failed 但标 recovered，全恢复则场景 passed）+ `min_passing`/`pass_ratio` 部分通过。
- **unconfigured 语义**：182 个场景中 165 个免配置可跑；16 个 env 门控的，缺 key 时整场景 `status="unconfigured"`、一个 step 都不执行、写明缺什么和 Director 该做什么——既不静默跳过也不假失败。
- **CI 硬接线（本体系最强的一环）**：`ci.yml:298` 每次PR 用 `scenario_portability_gate.py` 枚举 keyless 子集、逐个经真实 dispatch 执行，known-red 变绿即 CI 红；另有全库 `load_scenarios()` 解析步骤。回归场景事实上已成为"每次改代码必须过"的活资产。
- **MCP 自助测试**：`list_validation_scenarios` / `run_validation_scenario` / `run_all_validation_scenarios` / `get_run_decisions` 让 agent 从自己的操作面就能发起验证并拿机器可读判定——AC1 判据 2（"agent 可自验"）由此成立。

### 5.2 闲置的部分（循环层 ❌）

治理契约（`docs/dev/validation-governance.md`，2026-08-15 定稿）要求"循环前必读 5 项、循环后必产出 5 项（含 run 记录与 loop-log 坑清单）"。实际执行痕迹：

| 产物 | 最新时间 |
|---|---|
| `validation-runs/` 最后一次持久化 suite run | **2026-09-13 19:34**（`latest.txt`） |
| `validation-runs/sessions/` 结构化报告 | 2026-09-13 |
| `validation-loop-log.md` 最后一次实质循环记录 | **2026-09-14 循环**（其后 10-26 仅 1 行措辞清理） |
| `validation-deliveries/` 交付包 | 仅 1 份（2026-09-04），此后再无 |
| 最近一份正式验收报告 | `acceptance-1.14.0-2026-09-29.md` |

即：**"Agent as tester" 的完整治理循环（run_all → 持久化 → 报告 → loop-log → 交付包）自 9 月中之后 6 周没有发生过**。10 月的验证活动转到了另一条轻量轨道（`nightly_gap` 差距矩阵达 21/21、`capability-27x3` L0/L1 baseline，最新产物 2026-10-27/28）——活动存在，但治理文档规定的循环契约在无任何声明的情况下事实上中断了。契约没有任何机械触发器（不挂在 release、不挂在 CI、不挂在 cron），它的存续完全依赖 agent/指挥者记得。

公平地补一句：**场景文件本身仍在活跃迭代**（最近 commit 2026-10-28，回归场景从 9 月中的 ~75 个增至 96 个，10-26 还在修 hermetic 性）——作为 CI 测试资产，这套体系是活的；作为治理循环，它是停摆的。

---

## 6. 防漂移与验收机器：最强的仪器恰好都不在 CI

**🟡 `doc_inventory.py --check`——全仓最强的防漂移仪器，接线最弱。** 7 项检查覆盖：7 类漂移敏感事实（工具数/CLI 组数/场景数/demo 域数等）跨 9 份 LIVING_DOCS 与 README 对齐、server.py 实际工具列表 vs README **双向完备**、pytest 收集数一致、无游离 `test_bug_*`、inventory 本身逐字节一致。这类"从代码派生"的检查正是 AC8 判据 2 钦定的机制——但它在 `make doc-check` 里，**不在 CI**。

**🟡 guard.yml Drift Guard——CI 里唯一的文档强制，且结构上是块名单。** 它只能挡"历史上出现过、被拉黑"的字符串（三例：114+ 工具数、139 工具数、44 场景数等 12 个旧计数，均为英文字面拉黑）。从代码派生的漂移它管不到。实测残留证据：`docs/dev/specs/user-lifecycle-definition.md:51,219` 与 `:248` 仍写 "147 tools"/"147/147"（真实 149）；`docs/dev/acceptance-framework.md:181,463` 同样写 "147/147"——**验收框架自己的判据表与它 §0.2 的 "149 tools" 自相矛盾**。更讽刺的是 guard.yml 自己第 77 行注释里的 "(current: 47)" 也已漂移（现 182）。这正是 10-29 报告 P4 指出的"keystone 滞后"一类问题的继续发生：块名单是打地鼠，派生检查才是网。

**🟡 其余派生检查同样未进 CI**：`surface_parity.py --check`（REST 全路由对账，canonical 8 端点必须场景级覆盖——设计很好）；`coverage_matrix.py --check-enduser-doc`（99 项矩阵逐字节比对）；`coverage_matrix.py` 按版本重生成靠 AC4 判据 4 的 prose 职责（"stale matrix = RISK"——谁来判 RISK？还是 agent 记得跑）。

**🟡 AC1-AC9 框架——章程成色高，触发纯靠 prose。** 九维二元判据、A1-A24 可重跑证据目录、PASS/FAIL/RISK/unconfigured 语义、P5 "the agent grades; the human disposes"、§0.4 双取向层级（agent 证据不足以验收交付物）——这套章程把两个 agent 角色的关系写得很清楚，是全仓最有思想密度的文档之一。但它的触发器（§7.2 trigger 表：major/minor/wave）没有任何机械挂接：最近一份验收报告停在 1.14.0（2026-09-29），此后 1.15→1.21.4 七个版本没有验收报告。框架不会自己执行。

**🟡 scripts/ 长尾（40+ 脚本）**：`tool_desc_audit`、`error_message_audit`、`vendor_agnosticism_check`、`capability_matrix`、`scenario_outcome_audit`……多数是历次验证战役留下的可重跑证据机器，被 AC 证据目录 A1-A24 引用着，不算孤儿；但 Makefile 只暴露其中 2 个（validate/doc-check），"哪些是门禁、哪些是仪器、哪些是一次性工具"没有任何注册表——对一个面向 agent 的仓库，这个盘点本身就是 agent 需要而得不到的基础设施。

---

## 7. Skills 与 hooks：开发者侧活、operator 侧孤岛、强制层完整但有缺口

**✅ `.opencode/skills/`（4 个）——真技能。** deep-modules / doc-manager / maintainer-workflow / validation-runner，都在 OpenCode 的标准发现路径上、有 frontmatter、指回权威深度文档。两个问题：**(a) 单编辑器绑定**——Cursor/Claude 不会发现它们；**(b) gitignore 陷阱**——`.opencode/.gitignore` 第 7 行忽略 `skills/`（注释"never committed"），而这 4 个 SKILL.md 是被强制跟踪的：历史文件在，但**今天往里加的任何新技能会静默不入库**。

**❌ `docs/skills/`（2 个）——文档孤岛。** autoinfo-skill（约 40 个 MCP 配方 + 三层授权边界图，写得不错）连 frontmatter 都没有；translator-qa-skill 有 frontmatter 但路径不对。`docs/skills/` 不是任何 agent 技能加载器的发现路径，`src/`/`tests/`/CI 对它们 0 引用，AGENTS.md 只在目录树里列了个名（无加载指令）。它们唯一的"防遗忘"机制是被 doc_inventory 列入 LIVING_DOCS 做数字核对——而那个检查本身不在 CI。作为**参考文档**它们有价值（autoinfo-skill 的授权边界图和 product 模板差异说明是 AGENTS.md 没有的）；作为 **skill**（项目自己的定位："AutoInfo operator skills (for agent-users of AutoInfo)"）它们是无效的——一个 agent-as-user 永远不会"加载"到它们。这与 AGENTS.md 的定位（面向所有 agent 的手册）形成了分叉：agent 的实际入口是 MCP 协议发现 + （仅 OpenCode 的）AGENTS.md，operator skill 处在所有真实路径之外。

**✅ hooks/CI 强制层——完整度高于多数同类仓库。** pre-commit：ruff 0.17.1（与 pyproject 同 pin）+ ruff-format + gitleaks 8.18.4 + no-credential-url（本地层）；CI 8 条 workflow：lint（gitleaks+signoff+ruff 双范围）、mypy-changed-files（changed+full）、test（`pytest -m "not real_api"` = 6662/6665）、**scenario-portability**（见 §5）、**guard.yml**（防漂移 + 域表 + nightly ledger）、**coverage.yml**（baseline-aware 逐模块覆盖率门，双 worktree 对比——少见的好设计）、pr-title-check（Conventional Commits + release-scope）、release-please + 自动合并 + manifest 对账、nightly 全量、preview-smoke。发版闭环、版本真值、PR 纪律全部机械强制。

CI 的**缺口清单**（全部是"仪器存在、接线缺失"）：无 format 门（ruff format 存量 src/ 10 个文件）、无 doc_inventory、无 L0 quality_gate、无 L1 battery、无 surface_parity、无 ax_metrics、无 enduser 矩阵比对。另：仓库没有任何 agent-client hooks（.cursor/.claude 均无 hooks 配置）——"hooks"这一层在本项目 = git pre-commit + GitHub Actions，仅此两层。

---

## 8. 横向模式（比单点判定更重要的结论）

**模式一：机制层强，循环层弱。** 每一件基础设施的"实现质量"都在水准之上（引擎、仪器、章程、双层 QC 设计），但凡是需要"有人记得再跑一次"的环节——验证治理循环、验收报告、L0/L1、AX 度量——要么熄火要么从未点火。项目已经用 CI 解决了"代码改动被强制验证"，没有解决"产品与文档承诺被强制对账"。

**模式二：声明的强制等级系统性高于实际接线等级。** 本轮实锤四起：G4/G5 默认关（文档按默认开表述）、D1-D3 默认从不触发（文档写 "Blocks delivery"）、ax_metrics "CI enforces"（实际 0 接线）、frequency_gate docstring 虚构 MCP 路径。对普通项目这是文档债；对 agent-first 项目这是**行为性风险**——agent 没有"文档可能夸大"的先验，它按 AGENTS.md 行事。

**模式三：仪器层与强制层错位。** 全仓五件"从代码派生"的一等仪器（doc_inventory、surface_parity、coverage_matrix --check、ax_metrics、L0）恰好全部在 CI 之外；CI 里唯一的文档强制（guard.yml 块名单）恰好是五件里最弱的一种机制。而"147 tools"残留在两份 keystone 文档里存活至今，就是错位的直接后果。

**模式四：项目已写出了正确原则，但只对知识执行、没对检查执行。** AC8 的 knowledge-reachability 注（director 决策 2026-08-08）："critical knowledge must be **reachable by default** … not dependent on an agent's reliable invocation of an optional skill"。把这句话的主语换成"检查"同样成立：**强制性的检查不能依赖 agent 可靠地主动调用一个可选脚本**。operator skills 孤岛（知识侧违反）与 L0/ax_metrics 无接线（检查侧违反）是同一原则在两个层面的失守。

**模式五：唯一"纸面规则全部代码化"的领域（KB 管线）恰好也是治理最好的领域。** 01-Raw/晋升/Wiki 保护有代码强制 + 场景锁定 + ADR 记录 why。这证明团队有能力把 prose 升级为机制——其他领域（交付门禁、AX 度量、验收触发）缺的不是能力，是把同样的升级做完。

---

## 9. 对两个前提的回答

**"Agent as a user" 成立，且是仓库的强项**——前提是 agent 只依赖运行时面（MCP 工具 + envelope + KB 代码纪律 + 开箱配置），这些全部真实有效。但 agent 不可能只依赖运行时面：它还要读文档来决定"质量防线是否已在看守"。在这一层，它读到的是一张夸大的门禁表（G4/G5/D1-D3 的默认行为与表述不符）。

**"Agent as a tester" 机器层成立、循环层当前不成立**——场景引擎、CI portability 门、证据目录、coverage gate 是同类项目少见的完备；但完整治理循环停摆 6 周、最强仪器在 CI 外、AX 度量无扳机、验收框架不自我触发。当前的 agent-tester 更像：握着一整套精良但多数需要手动扣扳机的武器库，而最近六周没有扣过几次。

---

## 10. 建议（按性价比排序，P0 基本都是接线工作）

**P0 — 把仪器挂进 CI（一个 PR 能做完大半）：**
1. guard.yml 或新 job 加入：`doc_inventory.py --check`、`surface_parity.py --check`、`coverage_matrix.py --check-enduser-doc`。三者都是只读、keyless、秒级——接入成本最低、直接修复模式三。
2. 给 `ax_metrics.py` 二选一：真挂进 nightly/CI，或 docstring 改口为"手动仪器"。名实必须归一。
3. `quality_gate.py`（L0）对 `outputs/` 中有产物的域在 nightly 跑一轮并落档（作为仪器而非门禁），让 demo-release-standard 的 L0 checkbox 有机械兜底。

**P0 — 归一名实不符（纯文档/注释修正）：**
4. AGENTS.md 门禁表给 G4/G5/D1-D3 标注真实默认（"opt-in via --check-factual / config delivery_gates；当前 demo 默认未启用"），Quick Start 的 "# quality gates" 注释同步；acceptance-framework §5.1 补一句"hard 指执行时不可绕过，G4/G5 为 process 层 opt-in"。或者反向做：把 D1-D3 的默认阈值写进 `default_config.yaml`（有记录的默认），让文档成真——两者选一，不能维持现状。
5. 清理 "147" 残留（user-lifecycle-definition ×3、acceptance-framework ×2），并把这两份文档纳入 doc_inventory 的 LIVING_DOCS 数字核对，使块名单退役成为可能。
6. `frequency_gate.py` docstring 与 `scheduling.py` 现实对齐（要么补 MCP 接线，要么改 docstring）。

**P1 — 治理循环二选一，不许停在中间态：**
7. 验证治理循环：要么重启（把 `run_all_validation_scenarios` + loop-log 更新机械挂到 release 前置或 monthly cron），要么正式修订 `validation-governance.md` 为"按需触发"并归档旧承诺。契约有效但无人履行是最差状态——它让后来者无法区分"静默债务"和"设计如此"。
8. operator skills 归宿：给两份 SKILL.md 补 frontmatter 并移到 `.opencode/skills/`（或至少在 AGENTS.md 写明加载指令）；若决定不做 skill，就在 AGENTS.md 目录树里改标注为"参考文档"。

**P2：**
9. 修 `.opencode/.gitignore` 陷阱（对已跟踪的 4 个技能加否定模式或改注释）。
10. Makefile 加 `battery` target（L1 需要一个扳机点）。
11. 在 doc-inventory 或一个 `docs/dev/INFRA-REGISTRY.md` 里给 scripts/ 全量标注：gate / instrument / one-off + 当前接线状态——这份盘点本身是 agent 需要的基础设施。

---

## 附：证据清单（全部于 2026-10-30 在 HEAD `96f7fefe` 实测）

| 结论 | 证据 |
|---|---|
| G4/G5 默认关 | `src/autoinfo/mcp/tools/sources.py:578-594`（schema default False）；`src/autoinfo/cli/process.py:41-50`；`src/autoinfo/process.py:927` |
| G4 默认跑的唯一路径是晋升 | `src/autoinfo/promotion.py:199,217,264`（CurationGate G0+G4 复核） |
| D1-D3 默认从不触发 | `src/autoinfo/output/gates.py:29,331-336`（无配置返回 None）；`grep -r delivery_gates src/autoinfo/data/` = 0 命中；`mcp/context.py:742` 不传 |
| L0 仅 make validate | `.github/workflows/` grep quality_gate = 0；`Makefile:55-56` |
| L1 零接线 | workflows/Makefile grep battery = 0；`Makefile:57-59` 仅 echo；verdict 语义 `battery.py:262,504-509` |
| 盲点 20 条/10 family | `scripts/agent_review/blindspots.yaml`（183 行） |
| 验证循环熄火 | `validation-runs/latest.txt` = 2026-09-13_193459；`validation-loop-log.md` 最后实质循环 "2026-09-14"；`validation-deliveries/` 仅 20260904 一份 |
| CI 场景强制 | `.github/workflows/ci.yml:298`（scenario_portability_gate，真实 dispatch） |
| 场景规模与语义 | 182 = 86+96；16 env-gated / 165 keyless / 4 llm_assert；unconfigured 语义 `src/autoinfo/mcp/validation.py:1874` |
| doc_inventory 未进 CI | workflows grep doc_inventory = 0；`Makefile:65`（doc-check 三连） |
| guard.yml 块名单 + 自身注释漂移 | `.github/workflows/guard.yml:39-40,76-77`（"44 场景 (current: 47)"，实际 182） |
| "147" 残留 | `docs/dev/specs/user-lifecycle-definition.md:51,219,248`；`docs/dev/acceptance-framework.md:181,463` |
| ax_metrics 无接线 | workflows/Makefile grep ax_metrics = 0；docstring "targets that CI enforces"（`scripts/ax_metrics.py` 头部） |
| frequency_gate docstring 失实 | `src/autoinfo/delivery/frequency_gate.py` 模块 docstring；`grep frequency_gate src/autoinfo/mcp/tools/scheduling.py` = 0；唯一调用 `cli/cron.py:1100-1102` |
| gate_report 双格式与诚实声明 | `src/autoinfo/delivery/gate_report.py:486-492,598`；调用方 `cli/mvp.py:437,446`、`scripts/validation_delivery.py:41,623,1152` |
| KB 纪律代码化 | `src/autoinfo/promotion.py`（CurationGate）；`WIKI_PROTECTED`；场景 `director-backdoor.yaml` |
| operator skills 孤岛 | `docs/skills/autoinfo-skill/SKILL.md` 无 frontmatter；src/tests/workflows 引用 = 0；仅 AGENTS.md:98 目录树 + doc_inventory LIVING_DOCS |
| .opencode 陷阱 | `.opencode/.gitignore:7`（`skills/`）vs `git ls-files .opencode/skills/` = 4 个已跟踪 |
| AGENTS.md 单通道加载 | `.cursor/` 仅 mcp.json；`.claude/` 仅 Desktop 配置；无 CLAUDE.md；AGENTS.md 402 行 |
| CI 缺口 | workflows grep format/doc_inventory/quality_gate/surface_parity/ax_metrics = 全 0 |
| 验收报告断档 | `docs/dev/validation-reports/` 最新 acceptance 文档 = acceptance-1.14.0-2026-09-29.md（当前 1.21.4） |
