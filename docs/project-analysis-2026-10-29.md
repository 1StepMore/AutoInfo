# AutoInfo 项目理解与问题分析报告

**日期**：2026-10-29
**方法**：静态阅读核心文档（README / AGENTS.md / founder-expectations / cross-dimensional-catalog / 两份历史评估 / 残差登记表 / TRIAGE / pkg-AutoInfo 交付包）+ 对当前代码与本机仓库状态的实测核实（god module 行数、被跟踪文件、cost.py 缺陷、REST 鉴权、熔断器、配置缓存、静默吞异常、贡献者分布）
**与前两份评估的关系**：`docs/project-evaluation-2026-09-06.md`（首评）与 `docs/project-health-assessment-2026-09-17.md`（复测+当日修复）。本报告不重复其已修复项的论证过程，只核对修复是否落地，并把重心放在**当前**的问题上。

---

## 一、这个项目是做什么的

AutoInfo 是一个**通用信息追踪与知识库平台**：用户配置信源（sources）和关注主题（topics），平台自动完成**采集 → LLM 结构化提取 → 质量门禁 → 四层知识库沉淀 → 信息产品生成 → 多渠道分发**的全链路。它的自我定位是"信息助理"——不是帮你搜索，而是把从采集到知识沉淀的体力活全部自动化。

按 `founder-expectations.md` 的定义，它不是开发者工具，而是**面向付费客户的商业化内容工厂**：RAW 产品（原始信息流、API feed、批量导出）与 PROCESSED 产品（简报、专题报告、教程、告警流）都是一等公民，平台是工厂，产品是商品。demo 域（21 个：medical-research、ai-commercial、语言学习族等）只是配置示例，领域本身不写在代码里。

当前规模（2026-10-29，版本 1.21.4）：

| 维度 | 数值 |
|---|---|
| 源码 | 174 个 Python 文件 / 95,192 行 |
| MCP 工具 | 149 个（35 类），dispatch 注册表已从 if/elif 链重构（#581） |
| CLI | 31 个命令组 |
| 采集器 | 30 个 handler（PubMed、SEC EDGAR、RSS、Web、Bilibili 等） |
| 测试 | ~6,665 个用例 / 182 个验证场景（86 功能 + 96 回归） |
| 文档 | 126 份 / 38,972 行（含 11 份 ADR、12 份 spec；`docs/adr/` 下另有 README.md 与 TEMPLATE.md，非 ADR） |
| demo 域 | 21 个， curated sources 总计 100+ |

## 二、设计理念

1. **Agent-first（B1/B2/B3 三角色模型）**。系统的第一操作界面是 MCP 工具——149 个工具全部可被 AI agent 调用；CLI 只是人类的降级备选。人类"指挥者"（B3）用自然语言向 agent（B2）下达意图，agent 翻译成工具调用；"最终用户"（B1）只消费交付的产品。这是整个项目最根本的架构决策——连 AGENTS.md 本身都是写给 agent 的操作手册。

2. **领域无关**。加一个领域 = 加一份 `sources.yaml` 配置，不改代码。采集器通过 registry 查找（`collectors/registry.py`），加源 = 一个类 + 一次注册。

3. **产品优先 + 质量是硬约束**。质量门禁不是建议而是管道的一环：G0/G4 硬门禁（重试后阻断）、G1-G3/G5/G7 软门禁（可配置）、D1-D3 交付门禁；产品 QC 分三层（L0 确定性 gate → L1 可选 agent 语义评审 → ESCALATE 人类裁决），并明确"诚实的不确定（hedge）= 正确行为，不得标记"。

4. **KB 四层管道纪律**。01-Raw 是唯一入口（保证来源溯源完整），02-Draft 只能从 Raw 产生，03-Wiki 只增不删；Draft→Wiki 晋升是 **agent 操作、无人工闸**——因为 KB 被定义为"生产数据库"而非人工策展的知识库（2026-08-08 决策）。这条纪律有专门的验证场景（`director-backdoor.yaml`）锁住，不是纸面规定。

5. **BYOK + LLM 治理**。用户自带 key，平台只存 `${ENV}` 引用从不落原始密钥；所有 LLM 调用路径统一走 `call_with_fallback`（主模型 + fallback 链 + per-provider 信号量限流 + 429/5xx 抖动退避）；判断类调用钉死 release 级 `JUDGMENT_MODEL` 常量，防止运行时漂移。

6. **诚实工程（这是本项目最有辨识度的理念）**。"新问题无穷"的焦虑被制度化为三份登记：`tests/TRIAGE.md`（已知红灯预算，按测试 ID 锁定身份而非数量）、`docs/known-limitations/demo-quality-residuals.md`（产品质量残差登记：现象→类→检测层→严重度→状态）、gap register（带独立评审回执）。验证场景在环境缺依赖时报 `unconfigured` 而非静默通过；文档数字由 `doc_inventory --check` + guard.yml 防漂移；"登记在先、修复在后"是明确的流程要求。

7. **知识即资产**。实时 feed 是流量，积累的知识库才是长期资产——这句理念在第五节的问题分析里会被反复对照。

## 三、9-17 报告 P0 项的落地核实（本轮实测）

上一份健康度评估的同日修复声称解决了 5 项 P0/P1。本轮逐项验证，**全部属实**：

| 9-17 报告的问题 | 本轮实测结果 |
|---|---|
| `mcp/server.py` 11,863 行上帝模块 | **已拆分**：现为 1,147 行 hub（注册表 + 调度），handler 按 domain 拆到 `mcp/tools/`（#581） |
| `output/__init__.py` 9,336 行 | **已部分拆分**：现为 5,261 行（export/ebook/video/audio 等已独立成模块） |
| 6,905 个运行时产物被 git 跟踪 | **已清**：当前跟踪 1,090 个文件，`knowledge/collections/outputs/...` 命中 **0** |
| release-please 断线（当时停在 1.11.0） | **已恢复且运转正常**：现在 1.21.4，release PR 自动合并工作流在位（8 条 workflow） |
| mypy strict 192 错 / ruff 版本漂移 / 红灯预算只锁数量 | **已修**：mypy 全树 0 错、ruff 锁定 0.16.8、TRIAGE 预算已改为测试 ID 身份锁且 2026-10-12 起预算清零 |

工程卫生债在六周内被实质性清偿，这一点应当先于问题清单被承认。但清偿的是"机制层"的问题——下面是**当前**的问题。

---

## 四、当前问题分析

### P0（最核心）：机制规模与实际产出严重失衡——工厂建好了，订单没有流动

这是本轮分析最重要的发现，证据来自项目自己三天前生成的交付包（`pkg-AutoInfo/README.md`，2026-10-26，基于本机实跑 `coverage_matrix.py --evidence outputs`）：

| 生产能力矩阵（13 域 × 8 产品 × 8 格式 = 832 格） | 数量 |
|---|---|
| 有真实产物的格 | **29** |
| 空 gap（待补） | **322** |
| 组合不成立（N/A） | 481 |

非矩阵维度同样见底：

- **78 个"必达域×源"组合零原始数据**——要么源根本没配置（A 类），要么配置了采不到：反爬、GFW 封锁、feed 改版、超时（B 类）。
- **39 个 KB 层级（13 域 × Raw/Draft/Wiki）全部为空**。"知识即资产"是项目的核心理念，而资产目前账面为零。
- 14 个交付渠道、15 个能力**全部没有可执行的场景库**。

残差登记表里的两条近期记录把这条主线串成了因果链：ai-commercial 域仅有 5 条 KB 条目建于 2026-08-15，T11 采集到的 58 条新材料**卡在 gitignored 的 `collections/` 里无法入库**（缺 `AUTOINFO_LLM_API_KEY`，process 层跑不了），于是 7 个 digest 单元因"所有候选条目过期"被新鲜度闸门拒产。采集→处理→知识库→产品这条主干道，目前每一环都有数据流动的瓶颈。

两个旁证说明这不是纸面推断：其一，最近两次发版（1.21.3/1.21.4，10 月下旬）都在修 process 层的真实生产 bug——处理游标按 item id 单调推进（#637）、`--since-days/--newest-first` 让预算内的运行能触及新条目（#655）——说明生产运行真的在跑，且跑的时候暴露的都是"新内容到不了 KB"这一类洞；其二，README 的 demo 域表里大量源被标注 disabled（GFW-blocked / dead / 404），采集层在中国的网络环境下天然折损严重。

**一句话判断：项目用六周把"工程机制"做到了中大型开源项目水准（149 工具、6,665 测试、182 场景、3.9 万行文档），但"工厂产能"只兑现了 29/832——下一步的主要矛盾不在代码质量，而在让数据流过管道。** `pkg-AutoInfo` 交付包已经给出了正确的路线（T1 采集源诊断 → T2 分四批补 322 格 → T3 KB 层级 → T4 场景库），且把"每域至少 2 个稳定源"设为硬指标而非"78 全绿"，这个取舍是对的。

小瑕疵：该交付包引用的命令 `python -m autoinfo.cli gap` **并不存在**（`docs/dev/source-diagnosis.md` 已注明其被 `scripts/source_diagnosis.py` 取代）——三天前生成的交付包就已经和仓库有轻微漂移，这正好复现了残差登记表 C 节"文档与代码无对账"的那一类问题，只不过这次发生在交付包里。

### P1：已登记、至今未修的真实缺陷

1. **`src/autoinfo/cost.py:818` 双 WHERE SQL 缺陷**（2026-09-17 登记，六周未修）。`f"SELECT DISTINCT domain FROM cost_log{where} WHERE domain != ''"` 在 `where` 已含条件时拼出第二个 WHERE，`period="today|week|month"` 一律抛 `sqlite3.OperationalError`，被外层 `except Exception: pass` 吞掉——**预算告警（F45 的核心承诺）整条链路实际上从未工作过**。代码注释已自认这是"at least honest dead"的死代码块，但"登记未修"的状态意味着成本治理支柱里最关键的告警环节是空的。修法已在 TRIAGE 写明（复用 `where` 片段而不是追加），是个小改动。
2. **并发 outbox 写丢通知**（TRIAGE 2026-09-17 观察项）。16 线程并发写时 `1 of 16 events dropped`，且**明显诊断已被证伪**——`busy_timeout` 自 8 月 28 日起就在 WAL 之前设置，失败仍发生在 WAL 语句上，根因未定性。这是一条**真实的产品侧数据丢失路径**（丢的是最终用户的通知行），不是测试问题。需要专门的 16 线程复现来定性，一直以"负载敏感 flake"的身份挂着。
3. **canonical selection 之外的两个已知失败**（TRIAGE 在案）：`test_batch_size_passed_to_run_processing` 是一行 stale 测试修（断言缺 `resume_from` kwarg），但"没有任何东西盯着 canonical selection 之外的目录"；`test_generate_report_json_format` 依赖本地数据 + 真实 LLM key，在全量跑时会烧 230 秒退避后被 180s 超时杀死——后者是非封闭测试的另一员。
4. **`link_items` 不校验 relation type**（founder-expectations §14 自认的 v1.6+ 唯一残留）：`RelationType` 枚举存在但写路径放行任意字符串，低工作量，从 8 月挂到现在。

### P2：商业化路径上的架构性阻塞

1. **REST API 无鉴权**（本轮 grep 确认 `api/server.py` 无任何 auth/token/api_key 逻辑）。README 靠"默认绑 127.0.0.1"兜底，但平台的商业模型是 B1 付费客户通过渠道和门户消费——当前架构**无法安全对外托管**。
2. **多租户未实现**：`MultiUserConfig.enabled=False`，B1 的 KB 租户隔离在 cross-dimensional-catalog 里是 🔴；没有 auth/teams/RBAC。
3. **产品访问门禁只覆盖一半**：`check_access()` 在 output 层和 `list_output_templates` 上生效，但 MCP 产品生成工具（`generate_digest`/`generate_report` 等）上的门禁仍未 enforcing（founder-expectations §14 蓝色清单自认）——免费/付费分层在 agent 界面上是可绕过的。
4. **无提示注入防御**：采集来的外部文章直接进入提取/摘要 prompt，`llm.py`/`process.py` 无任何 sanitize 或指令隔离层（本轮 grep 0 命中）。残差登记表显示红队**验证场景**覆盖了注入类攻击（能检测），但防御层不存在。对一个"把互联网内容喂给 LLM 再把产物卖给付费客户"的平台，这是结构性风险。
5. **无熔断器**：持续失败的源不会被自动节流（`get_source_health` 只报告不干预），反爬致死的源会持续消耗采集线程与下游 LLM token。

### P3：质量门禁的已知盲区（残差登记表在案，此处汇总现状）

- **G7 抓不住编造年份**：`_REL_TOLERANCE=0.05` 的容差匹配让"won the 2031 World Cup"这类编造年份在含 2015–2027 数值的源文里全部"命中"。#444 注入实测检出率仅 **69.4%**；已裁决不升级为 block（否则 30% 编造年份照常通过、还把年份声明全面变成阻断面）。真正的修法是年份精确比对，尚未排期。这是"产物卖给付费客户"场景下最伤的盲区——数字幻觉里最难看出来的就是年份。
- **D2 orphan-entity 误报 ~27%**，只能 escalate 不能阻断，每轮产生人工裁决负担；H1/H2 gate 的良性误报同样每轮需人工过目。
- **三类单元处于"未验证"状态**：3 个 `report:video`（本机无完整 Chrome）、7 个 ai-commercial digest（上游 KB 陈旧，补 key 后必须先 process 再重跑）、MOBI 成功路径（CI 不装 calibre，README 已诚实降级为 🟡）。

### P4：工程流程与文档债

1. **双 agent 并行写 + release PR 自动合并的持续摩擦**：AGENTS.md 自己承认每次合并前必须 rebase 到最新 main（否则 ruleset 直接拒绝），而 release PR 在 main 上的每次 push 后数分钟内自动合并、使所有 open PR 的基线失效——预算"~20 分钟完整 CI 周期"。官方缓解手段是"更少更大的 PR"，这与"大 PR 高风险"存在张力，是制度性成本而非一次性成本。
2. **全量测试 55 分钟**，CI 只能跑快子集；负载敏感 flake（EPUB 边界、16 线程 outbox）在机器繁忙时会伪装成回归。
3. **keystone 文档滞后**：`cross-dimensional-catalog.md`（126 格产品矩阵、42 个 gap 的单一事实源）最后更新 2026-08-12，落后当前版本两个半月——而项目恰恰在这六周里把最大的 gap（生产能力）暴露了出来，矩阵里的 🟢/🟡/🔴 分布已经不可信。
4. **文档体量与版本堆积**：126 份 / 3.9 万行；`AutoInfo-development-brief-v2/v3/v4` 三版并存（9-17 报告已指出）。**已于 2026-10-29 处理**：v2/v3 与旧版 `AutoInfo开发简报.md` 移入 `docs/archive/`，v4 保留为唯一活文档；对新人（和 agent）的检索成本持续上升。
5. **`ruff format` 无 CI 门禁**：HEAD 上仍有一个待格式化文件存量（9-17 时 71 个、清偿后剩 46 个），pre-commit 只处理被暂存文件，任何人触碰这些文件都会带出整文件重排的噪音 diff。

### P5：治理风险

- **bus factor ≈ 1**：非合并提交中 renanzai(524) + renanzai40(44) = 568 条来自同一人（两个账号），1StepMore(244) 与 Hermes Agent(78) 是 agent/组织账号。实质性人类贡献者 1–2 人。项目的方法论文档化程度很高（这是对冲），但"两个 agent 写同一个仓库"的流程本身依赖唯一的人类指挥者持续在线。
- 工作区当前的未跟踪产物（`pkg-AutoInfo/`、`pkg-AutoInfo.zip`）尚无归属约定——它既不是 `.omo/` 那样的已定义运行时空间，也没进 git；按残差登记表的纪律，这类"新生表面"应当先登记归属再膨胀。

---

## 五、值得肯定的部分（避免失衡的画像）

- **诚实机制是同类项目少见的**：残差登记表、TRIAGE 身份锁、`unconfigured ≠ pass`、防漂移门禁、"登记在先修复在后"，构成了一套把未知逐步变成已知的制度，且本轮核实显示这些制度**真的在被执行**（预算清零、P0 清偿都有证据链）。
- **9-17 评估的修复质量高**：mypy 清偿不是逐条 suppress 而是按根因批量复位，过程中还挖出 6 个被 mock 掩盖的真实运行时缺陷并修复——这种"修债修出真 bug"的路径说明团队对债的态度是认真的。
- **发布自动化已闭环**：release-please + 自动合并工作流运转正常，版本真值清晰。

## 六、总体判断与建议方向

**总体判断**：AutoInfo 的工程机制成熟度已经明显高于它的实际产能。六周前的主要矛盾（工程卫生、上帝模块、发布断线、红灯预算）已被有效清偿；当前的主要矛盾是**"从会跑的工厂到有产出的工厂"**——832 格里 29 格的产能、空的 KB、零原始数据的 78 个源，才是"知识即资产"这个故事能否成立的唯一判据。同时有一条必须点名的暗线：**预算告警链路死亡（cost.py）+ REST 无鉴权 + 提示注入无防御**三者共同意味着，这个定位"付费客户平台"的系统，当前在"收钱、看住钱、安全地处理外部内容"三个环节都还是开发机姿态。

**建议优先级**（与 `pkg-AutoInfo` 交付包的 T1-T4 路线不冲突，是补充）：

1. **按交付包执行生产补齐**（T1 采集源 A/B 诊断 → T2 补 322 格 → T3 KB 层级 → T4 场景库），把 `source_diagnosis.md` 的 78 行表作为第一交付物。
2. **顺手修 `cost.py:818`**（一行改动，TRIAGE 已写明修法）——生产补齐会真实产生成本数据，预算告警不该在此期间保持死亡。
3. **为 outbox 并发丢通知立 16 线程复现**（TRIAGE 自己的要求）：生产补齐后通知量会上升，这条数据丢失路径从"负载下偶发"变成"必然暴露"。
4. **在对外托管 / 首个真实付费用户之前**：REST 鉴权 + MCP 产品工具的 check_access enforcing + 提示输入的隔离层，三件至少要有最小版本。
5. **刷新 keystone 矩阵**：cross-dimensional-catalog 停在 8-12，而它是所有 gap 的单一事实源——T2 的 322 格工作本身就是对它的大规模更新，应同轮完成。
6. G7 年份精确比对进入排期（残差登记已给出方案：年份不做容差、与来源年份集合等值判定），排在"产物开始交付给真实用户"之前即可。

---

## 附：本报告的证据清单

| 结论 | 证据 |
|---|---|
| god module 已拆分 | `wc -l`：server.py 1,147 / output/__init__.py 5,261 |
| 运行时产物已出跟踪 | `git ls-files` 1,090 条，运行时目录命中 0 |
| cost.py 缺陷仍在 | `src/autoinfo/cost.py:818` 及其上方"at least honest dead"注释 |
| REST 无鉴权 | grep `auth|api_key|token` 于 `api/server.py` 0 命中 |
| 无熔断器 | grep `circuit.?breaker` 于 src 0 命中 |
| 无提示注入防御 | grep `prompt.?injection|sanitiz` 于 llm.py / process.py 0 命中 |
| kb.py 静默吞异常 | `except Exception:` 25 处（9-17 时 21 处，**略有回升**） |
| 产能缺口 | `pkg-AutoInfo/README.md`（2026-10-26 实测）+ gap_cells.csv 322 行 |
| 发布正常 | git log：1.18.1→1.21.4 连续发版，release-please.yml / release-pr-auto-merge.yml 在位 |
| bus factor | `git log --format=%an` 统计（共 1,000 提交） |
| 交付包命令漂移 | `docs/dev/source-diagnosis.md` 明确记载 `autoinfo gap` 命令不存在 |
