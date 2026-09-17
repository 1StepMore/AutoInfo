# AutoInfo 项目健康度评估报告

**日期**：2026-09-17
**范围**：全维度评估 —— 代码架构、测试与验证、文档一致性、工程流程、安全合规、仓库卫生、治理可持续性
**方法**：静态代码审查 + WSL 真实环境实跑测试套件 + 工具链校验（ruff / mypy / coverage / doc_inventory / coverage_audit）
**评分口径**：1–10 分制 | **10** = 卓越 | **7** = 强 | **5** = 及格 | **<5** = 令人担忧

> 本报告所有数字均为**本轮实测**，非引用文档声称值。上一份同类报告为
> [`docs/project-evaluation-2026-09-06.md`](project-evaluation-2026-09-06.md)，两者差异在 §7 对比。

---

## 1. 总览评分

| 维度 | 评分 | 一句话结论 |
|---|---|---|
| 代码架构 | **5.5 / 10** | 模块划分清晰，但存在两个巨型"上帝模块" |
| 测试与验证 | **7.5 / 10** | 量足、可复现性强，但套件不封闭且全量跑 55 分钟 |
| 文档与一致性 | **6.5 / 10** | 三层防漂移机制很先进，但当前**已处于红灯** |
| CI/CD 与工程流程 | **6.5 / 10** | 门禁设计优秀，但只守"改动文件"，存量债不可见 |
| 安全与合规 | **7.0 / 10** | 密钥治理到位；REST 鉴权与多租户缺失 |
| 仓库 / 运行时卫生 | **3.5 / 10** | **最短板**：88% 的被跟踪文件是运行时产物 |
| 治理与可持续性 | **5.5 / 10** | 流程严谨度高，但 bus factor ≈ 1 |
| **综合** | **6.0 / 10** | **功能与流程成熟，工程卫生与静态质量拖后腿** |

**总体判断**：AutoInfo 是典型的**"流程成熟度远高于工程卫生度"**项目 —— 验证场景、残差登记、
独立评审、防漂移守护等机制达到中大型开源项目水准；但 88% 的仓库内容是运行时数据、
40% 的文件过不了自己的严格类型门禁、最核心的 MCP 层是一个 11,863 行的上帝模块。
**当前状态：能跑、能自证，但不好改。**

---

## 2. 实测数据汇总

| 指标 | 实测值 |
|---|---|
| 测试收集数 | **5,231**（README 声称 5,222 → 不一致，见 §4） |
| 全量套件 | **28 failed / 5,152 passed / 51 skipped，耗时 55 分 05 秒**（通过率 98.5%） |
| 核心选取集（mcp+validation+cli+output+llm） | **17 failed / 2,559 passed / 24 skipped，10 分 31 秒** |
| 覆盖率（同核心选取集） | **53%**（30,219 语句 / 14,245 未覆盖） |
| 源码规模 | 140 文件 / 77,479 行 |
| 测试规模 | 301 文件 / 96,623 行（测试:代码 = **1.25 : 1**） |
| 验证场景 | **161**（86 功能 + 75 回归） |
| 工具覆盖 | **147 / 149** MCP 工具被场景覆盖；**13 / 13** demo 领域覆盖 |
| ruff（本地 0.9.10） | src **48** 错误 / tests **259** 错误 |
| mypy strict | **192 错误，涉及 57 / 140 文件**（40% 文件未过严格类型检查） |
| 静默吞异常 | **67 处 / 23 文件**（`except Exception: pass` 形式） |
| 提交节奏 | 742 commits / 59 天（2026-07-20 起），8 月单月 431 次 |

**关键可复现性证据**：核心选取集的失败数 **17** 与 `tests/TRIAGE.md` 记录的基线
**完全一致** —— 说明项目的"已知红灯预算"是真实可复现的，不是账面数字。这一点值得肯定。

---

## 3. 逐维度分析

### 3.1 代码架构 —— 5.5 / 10

**做得好的部分**：

- `collectors/`（30 个 handler 各自独立成文件）、`output/` 已拆出
  `export.py` / `entries.py` / `ebook.py` / `video.py` / `seo.py`、`delivery/` 与 `delivery.py` 分层。
- 7 份 ADR 记录了"为什么这么设计"，不是只记"怎么做的"。
- KB 四层管道的硬约束（"仅 01-Raw 入口"、"03-Wiki 只增"）**有专门验证场景守护** ——
  `src/autoinfo/mcp/scenarios/director-backdoor.yaml` 验证 `force_promote` / `demote_kb_wiki`
  仅 director 可用。**架构规则不是写在文档里，是被测试锁住的。**

**核心问题：两个上帝模块**

| 文件 | 行数 | 结构特征 |
|---|---:|---|
| `src/autoinfo/mcp/server.py` | **11,863** | 149 个 `if/elif name ==` 分发分支 + 149 个 `_handle_*` 函数，全在一个文件 |
| `src/autoinfo/output/__init__.py` | **9,336** | 同时承载 digest / report / tutorial / presentation / product 多产品线实现 |

这两处的**改动爆炸半径极大**：新增一个 MCP 工具必须同时修改工具声明表、
`call_tool()` 调度链、权限白名单至少 3 处，极易漏改。

**类型与异常债**：

- mypy strict 192 错，40% 的文件未通过项目自己声明的严格模式。
- `except Exception: pass` 静默吞异常 **67 处 / 23 文件**，其中
  `src/autoinfo/kb.py` 一个文件占 **21 处** —— 核心 KB 模块静默吞异常是最值得警惕的一处。

### 3.2 测试与验证 —— 7.5 / 10

**强项**：161 个验证场景全部是"真调用 + 断言信封"，环境缺依赖时报告
`unconfigured` 而**不是静默通过** —— 这是少见的诚实验证设计。回归飞轮
（bug 模板强制填写回归场景）也已闭环，覆盖审计显示 0 个工具缺失覆盖。

**问题一：套件不封闭（hermeticity）**

`tests/TRIAGE.md` 自认有 9 个顺序依赖的假红；本轮实测复现了同类现象：
`tests/llm/test_simplify.py` ×7 + `tests/llm/test_llm_timeout.py` ×2。
**同一个用例单跑绿、合跑红**，说明存在跨用例状态泄漏（模块级全局状态、
未还原的 `os.chdir`、共享缓存等）。

**问题二：失败集合在轮换（最容易被忽视的盲点）**

已知红灯总数仍是 17，但**成分已经和 `tests/TRIAGE.md` 表格对不上**：

| 用例 | TRIAGE 记录 | 本轮实测 |
|---|---|---|
| `test_magazine_digest.py` | 2 | 3 |
| `test_fallback_config.py` | 2 | 3 |
| `test_tutorial_no_placeholder.py` | 3 | 0 |
| `test_coverage_matrix.py` | 1 | 0 |
| `test_doc_inventory_check.py` | — | **1（新增）** |
| `test_known_red_budget_single_source.py` | — | **1（新增）** |

**结论**：预算只锁"数量"、不锁"测试身份"，导致**新失败可以被旧失败的消失抵消而无人察觉**。

**问题三：运行成本与覆盖率盲区**

全量套件 55 分钟，CI 只能跑"快子集"；仓库级覆盖率**没有门禁**，
因此不存在任何官方覆盖率数字（53% 是本轮在核心选取集上实测的）。

### 3.3 文档与一致性 —— 6.5 / 10

**三层防漂移机制**（这是同规模项目里最强的一档）：

1. `scripts/doc_inventory.py --check` —— 校验 README / AGENTS.md / SKILL.md 之间的计数一致性
2. `.github/workflows/guard.yml` —— 扫描禁用字符串，防止陈旧声明复活
3. `make doc-check` —— 本地一键跑上述两项 + 覆盖矩阵校验

**但它现在红了，而且是自己人踩的**：

| 失败用例 | 事实 |
|---|---|
| `tests/validation/test_doc_inventory_check.py` | README 写 5,222 测试，实际 5,231。上一次"同步计数"提交 b803aa4 于 9-14 落地，**两天内又漂了** —— 说明提交前没人跑 `make doc-check` |
| `tests/validation/test_known_red_budget_single_source.py` | 该守护测试要求 `ci.yml` 不得复述失败预算数字，但 `ci.yml` 第 83 行仍保留 "M1-deferred" 字样 —— **守护测试与它要守护的文件自相矛盾**（提交 8edb5d4 只落了测试，没清理 ci.yml） |

**其他可读性问题**：

- `README.md` 的 Known Limitations 章节已退化成一整段按时间罗列场景数量的流水账，可读性很差。
- `docs/dev/` 下 `AutoInfo-development-brief-v2/v3/v4` 三个版本并存，旧版未归档。

### 3.4 CI/CD 与工程流程 —— 6.5 / 10

**强项**：6 条工作流（ci / coverage / guard / nightly / pr-title-check / release-please），
包含变更文件 ruff + mypy 门禁、**场景可移植性证明作业**、**基线感知的覆盖率门禁**、
文档漂移守护、dependabot 依赖自动更新、release-please 版本管理。

**问题**：

| 问题 | 说明 |
|---|---|
| 全树 lint 仅信息级 | `ci.yml` 中 `ruff check src/ tests/` 带 `continue-on-error: true`，存量债在 CI 里**完全不显示** |
| linter 版本未锁 | `pyproject.toml` 写 `ruff>=0.5`。本地 0.9.10 报 307 错，CI 注释说 0.15.22 报 863 错 —— **同一仓库两个数字，指标不可比** |
| 债务被"制度化" | `pyproject.toml` 为 `server.py`（214 行问题）和 `video.py`（39 行）写了永久豁免，而非修复 |
| 发布节奏滞后 | 最新正式版 1.11.0 停在 2026-08-19，`[Unreleased]` 已积累近一个月 |
| 远端状态不可查 | 本地环境无 `gh` CLI，GitHub Actions 历史结论无法从本地验证（本轮未验证） |

### 3.5 安全与合规 —— 7.0 / 10

**强项**：

- 三层密钥防护：gitleaks 预提交 + CI 双保险、本地凭证 URL 兜底钩子、`detect-private-key`。
- BYOK 只存环境变量引用（`${AUTOINFO_LLM_API_KEY}`），**从不落原始密钥**。
- 追加式审计日志、GDPR 数据导出、软删除、分层保留策略。
- 红队场景层已覆盖：提示注入、提示逃逸、数据外泄、工具参数滥用。

**缺口**：

- **REST API 无鉴权**（README 自述 "localhost security"）。
- `MultiUserConfig.enabled=False`，多租户 / RBAC 仍是规划态。
- 综合影响：**当前架构无法安全地对外托管**，是商业化路径上的硬阻塞。

### 3.6 仓库 / 运行时卫生 —— 3.5 / 10 ← **最短板**

这一条最严重，且与 `AGENTS.md` 的自我声明**直接冲突**。

`AGENTS.md` 明确声明 `collections/` `knowledge/` `outputs/` `.omo/` 是
"gitignored 运行时产物，不是源码"，`.gitignore` 也确实忽略了它们 ——
**但仓库里被 git 跟踪的文件中有 6,905 个属于这些目录**（这些文件在 ignore 规则
加入之前就已被提交，而 git 对已有跟踪记录的文件不会再应用 ignore）：

| 目录 | 被跟踪文件数 | 与 `AGENTS.md` 声明的关系 |
|---|---:|---|
| `knowledge/` | 3,867 | **违反**（声明为运行时产物） |
| `collections/` | 2,685 | **违反** |
| `outputs/` | 260 | **违反** |
| `validation-runs/` | 84 | **违反** |
| `.omo/` | 69 | **违反**（`.omo/plans`、`.omo/notepads`、`.omo/scripts` 不在豁免白名单内） |
| `validation-deliveries/` | 3 | **违反**，且含 **2 个 ZIP 二进制文件** |
| **合计** | **6,905 / 7,828 = 88%** | |

**连带后果**：

1. 工作区**永远脏** —— 本轮 `git status` 有 36 个改动，全部是 `_runs.json`、KB `.md`
   这类运行时抖动，导致"仓库干净"这条交付 DoD **在物理上永远无法达成**。
2. 任何"改动文件"门禁的 diff 噪音被放大，评审时难以分辨真实源码改动。
3. 仓库体积虚高（`.git` 44.8 MB），克隆与检索成本上升。

### 3.7 治理与可持续性 —— 5.5 / 10

**强项（这是项目真正的护城河）**：

- 7 阶段工作流宪章 + ADR-0006 落地，开发方法论有成文文件。
- gap register 带**独立评审回执**（Momus / Oracle 三轮评审，逐条记录缺陷与处置）。
- `docs/known-limitations/demo-quality-residuals.md` 把"新问题无穷"的焦虑转成了
  可枚举、有检测层、有严重度的**已知残余登记表** —— 这套方法论成熟度远超项目 2 个月的年龄。

**风险**：

| 风险 | 证据 |
|---|---|
| **bus factor ≈ 1** | 742 次提交中，`renanzai`(508) + `renanzai40`(45) = **74.5%**；`1StepMore` 126；`Hermes Agent` 93（agent 提交）；机器人 13。实质性人类贡献者 1–2 人 |
| 元数据失真 | `pyproject.toml` 仍写 `Development Status :: 1 - Planning`，而实际已是 1.11.0 / 149 个 MCP 工具的产品 |
| 文档体量与年龄不成比例 | 100 份 md 文档；单 `expectations.md` 167 KB —— 新人上手成本高 |

---

## 4. 问题优先级清单

| 优先级 | 问题 | 位置 | 修复成本 |
|---|---|---|---|
| **P0** | 6,905 个运行时文件被跟踪，工作区永久脏 | 全仓 | 高（需分批 `git rm --cached` + 确认） |
| **P0** | CI 当前红灯：计数漂移 + 预算守护自相矛盾 | `.github/workflows/ci.yml:83`、`README.md` 计数 | 低（改 2 处文本） |
| **P1** | 套件不封闭：9 个顺序依赖假红 | `tests/llm/` | 中（需定位状态泄漏源） |
| **P1** | 已知红灯预算只锁"数量"不锁"身份" | `tests/TRIAGE.md` | 中（预算改为记录测试 ID 集合） |
| **P1** | mypy strict 192 错、40% 文件未过 | 57 个文件 | 高（需分批清偿） |
| **P2** | `server.py` / `output/__init__.py` 上帝模块 | 2 个文件 | 高（需架构重构） |
| **P2** | 67 处静默吞异常（`kb.py` 占 21 处） | 23 个文件 | 中 |
| **P2** | 无仓库级覆盖率门禁（实测 53%） | `coverage.yml` | 中 |
| **P3** | REST 无鉴权 / 多租户未实现 | `src/autoinfo/api/` | 高（阻塞商业化） |
| **P3** | ruff 版本未锁、全树 lint 仅信息级 | `pyproject.toml` / `ci.yml` | 低 |
| **P3** | 发布滞后一个月、bus factor 1 | — | 流程性 |

---

## 5. 建议与倾向性判断

| 方案 | 优点 | 缺点 | 倾向 |
|---|---|---|---|
| **A. 先清卫生债 + 修红灯** | 解锁"仓库干净"DoD；门禁重新可信；成本极低 | 不解决深层质量债 | ✅ **强烈推荐先做** |
| **B. 先重构上帝模块** | 根治改动爆炸半径 | 11,863 行文件拆分风险极高，且会冲掉当前 17 个基线失败 | ❌ 暂缓，等 A 完成 |
| **C. 先补覆盖率与 mypy 门禁** | 抑制新增债 | 存量 192 错会让门禁长期红，需先做"只算新增"的基线感知门禁 | 🟡 可与 A 并行 |

**具体动作建议**：

1. **立即修 2 个红灯**（改 README 计数、删除 `ci.yml` 的 "M1-deferred" 段落），
   让 CI 回到绿 —— 这是唯一"零风险高收益"的动作。
2. **把已知红灯预算从"数量"改为"测试 ID 集合"**。当前 `17 = 17` 的巧合
   正在掩盖失败轮换，这是最容易被忽视的系统性盲点。
3. **清理被跟踪的运行时产物**，并把该检查加进 `guard.yml`
   （`git ls-files` 命中 ignore 目录即失败）—— 否则半年后会复发。
4. **上帝模块重构推迟**，但先立一条约束：新 MCP 工具不得再往 `server.py` 的
   `if/elif` 链里加分支（可先抽注册表，让调度与实现解耦）。
5. **锁定 ruff 版本**，否则 lint 指标永远不可比。

---

## 6. 与其他文档的关系

| 文档 | 关系 |
|---|---|
| `docs/project-evaluation-2026-09-06.md` | 上一份全维度评估（英文）；本报告是其 11 天后的复测 |
| `tests/TRIAGE.md` | 已知红灯预算的唯一权威来源；本报告 §3.2 指出其"只记数量"的缺陷 |
| `docs/known-limitations/demo-quality-residuals.md` | 产品内容质量的残余风险登记表（与本报告的工程健康度互补） |
| `AGENTS.md` | 声明了运行时产物与源码的边界；本报告 §3.6 指出实际仓库违反该边界 |
| `docs/demo-release-standard.md` | Demo 发布 DoD；本报告 §3.6 指出"仓库干净"一条当前无法达成 |

---

## 7. 与 2026-09-06 评估的对比

| 指标 | 2026-09-06 | 2026-09-17（本轮） | 趋势 |
|---|---|---|---|
| 测试总数 | 4,926 | **5,231** | ↗ 增长 |
| 已知失败数 | 17–18 | **17**（核心选取集） | → 持平 |
| lint 错误（全树） | 863 | 307（本地 ruff 0.9.10） | 指标口径不可比（版本未锁） |
| `output/__init__.py` | ~13K 行 | **9,336 行** | ↘ 已部分拆分 |
| `server.py` | ~12K 行 | **11,863 行** | → 未改善 |
| MCP 工具数 | 146 | **149** | ↗ |
| 验证场景数 | 138 | **161** | ↗ |
| 仓库卫生 | 未评估 | **6,905 个运行时文件被跟踪** | 新发现的系统性问题 |

**一句话**：功能面持续健康增长，已知缺陷数被有效控制，但**工程卫生债与静态质量债
两轮评估之间没有实质性改善**。

---

## 8. 本次评估的边界与未验证项

- REST API 与真实 LLM 调用**未做联网功能验证**（仅静态审查 + 单元/集成测试）。
- GitHub Actions 远端执行历史**未验证**（本地无 `gh` CLI）。
- `.omo/` 目录属 agent 编排层工作记录——**仅读取、未修改**（仅将其从 git 索引移出，
  磁盘内容原样保留）；`tests/TRIAGE.md` 在 §9 的修复中作为**红灯预算唯一来源**被更新。
- 覆盖率 53% 是**在核心选取集上测得**，非仓库全量；仓库级覆盖率因无门禁而不存在官方数字。
- 未做依赖漏洞扫描（本地无 `pip-audit` / 网络受限）。

---

## 9. 修复进展（2026-09-17 同日实施）

§5 的建议动作 1–5 已全部落地。P2（上帝模块重构、静默吞异常、仓库级覆盖率门禁）
与 P3（REST 鉴权 / 多租户）按约定不在本轮范围。

### 9.1 动作清单与结果

| 建议动作 | 落地内容 | 验证证据 |
|---|---|---|
| 1. 立即修 2 个红灯 | README / AGENTS.md / doc-manager SKILL 的测试计数统一为 **5237**；`ci.yml` 删除复述红灯预算的注释块与失败提示行，改为指向 `tests/TRIAGE.md` | `scripts/doc_inventory.py --check` → exit 0；`coverage_matrix.py --check-enduser-doc` → OK；2 个漂移守护测试转绿 |
| 2. 预算由「数量」改为「测试身份」 | `tests/TRIAGE.md §Authoritative known-red budget` 现枚举 **6 条确切 node id**（不再是裸数字）；守护测试断言「列表非空 / 无重复 / 每个 id 都能落到磁盘上的真实测试 / 基线失败数 == 列表长度」 | `tests/validation/test_known_red_budget_single_source.py` 4 passed |
| 3. 清理被跟踪的运行时产物 | `git rm -r --cached` 移出 `knowledge/` `collections/` `outputs/` `validation-runs/` `validation-deliveries/` `.omo/` 共 **6,968** 个文件（磁盘文件全部保留，已核验）；新增守护测试锁住该边界 | 跟踪文件 **7,828 → 860**；`tests/validation/test_tracked_runtime_artifacts.py` 2 passed |
| 4. 上帝模块：先立约束、重构推迟 | 新增 `tests/mcp/test_server_dispatch_freeze.py`：`server.py` 的 `if/elif name ==` 分支数与 `_handle_*` 函数数**冻结在 149**；新增工具必须先抽注册表，否则守护测试转红 | 2 passed |
| 5. 锁定 ruff 版本 | `pyproject.toml` 由 `ruff>=0.5` 改为 `ruff==0.16.8`；`ci.yml` / `coverage.yml` 中互相矛盾的历史计数（863 与 211）统一为**同一锁定口径下的实测值 309** | `ruff check --select E9,F src/` → All checks passed |

### 9.2 意外收获：套件不封闭的根因不在测试，在源码

§3.2 记录的 9 个「顺序依赖假红」本轮被**定位并根治**：

- **根因**：`LLMExtractor._get_litellm()` 对 LiteLLM 的日志句柄调用
  `StreamHandler.setStream(sys.stderr)`。`setStream` 会先 flush **旧** 流；当此前的
  CLI 测试在捕获环境下把该句柄绑到 pytest 的捕获流、测试结束后该流被关闭，
  下一次调用就会在 flush 阶段抛 `ValueError: I/O operation on closed file`，
  并且是在 `litellm.completion` **之前**中断整条 LLM 调用链。
- **实测证据**（`pytest tests/cli tests/llm/test_simplify.py`，修复前）：
  `WARNING autoinfo.output: LLM simplification failed: I/O operation on closed file.` → 7 failed。
- **修复**：`src/autoinfo/llm.py` 对 `setStream` 增加 `ValueError` 兜底 ——
  丢弃已死句柄并在其后重建一个。这既消除了跨测试状态泄漏，也修掉了一个真实的生产脆弱点：
  只要 `stderr` 被关闭/替换，所有 LLM 调用都会静默失败并退化为「原样返回」。

### 9.3 复测数字

| 指标 | 修复前（本报告 §2） | 修复后（同日复测） |
|---|---|---|
| 核心选取集失败数 | 17 | **6** |
| － 其中顺序依赖假红 | 9 | **0** |
| 被跟踪文件数 | 7,828（含 6,968 运行时产物） | **860** |
| `git status` 条目 | 36（全为运行时抖动） | **6**（全部为本次有意改动） |
| ruff 口径 | 0.9.10 → 307 / 注释称 0.15.22 → 863 | **0.16.8 → 309（版本已锁）** |

核心选取集残留的 6 条红灯已逐条登记在 `tests/TRIAGE.md`，性质为
「依赖本机配置 / 本机数据集」，非顺序依赖。

### 9.4 未做项（明确排除）

| 项 | 原因 |
|---|---|
| `server.py` / `output/__init__.py` 拆分 | §5 方案 B：风险高，先以 149 冻结约束兜住增量 |
| 67 处静默吞异常、仓库级覆盖率门禁 | P2，本轮范围外 |
| REST 鉴权 / 多租户 | P3，阻塞商业化的独立工作项 |
| mypy strict 192 错清偿 | P1 但成本高，需分批；本轮先锁定 ruff 口径与红灯身份 |
