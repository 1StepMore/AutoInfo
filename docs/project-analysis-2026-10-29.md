# AutoInfo 项目理解与问题分析报告

**日期**：2026-10-29（**2026-10-30 复核并修正**，见下方"修订记录"）
**方法**：静态阅读核心文档（README / AGENTS.md / founder-expectations / cross-dimensional-catalog / 两份历史评估 / 残差登记表 / TRIAGE / pkg-AutoInfo 交付包）+ 对当前代码与本机仓库状态的实测核实（god module 行数、被跟踪文件、cost.py 缺陷、REST 鉴权、熔断器、配置缓存、静默吞异常、贡献者分布）
**与前两份评估的关系**：`docs/project-evaluation-2026-09-06.md`（首评）与 `docs/project-health-assessment-2026-09-17.md`（复测+当日修复）。本报告不重复其已修复项的论证过程，只核对修复是否落地，并把重心放在**当前**的问题上。

## 修订记录

**2026-10-30 复核（HEAD `96f7fefe`，v1.21.4）**：本报告的每一处数字被逐条重跑复算，共修正 **12 项**——8 项事实错误（数字或结论与当前树矛盾）+ 4 项机制/口径偏差（方向对、归因不完整）。全部已在下文就地修正，原文判断保留但标注了修正理由。

| 原结论 | 复核结果 | 成因 |
|---|---|---|
| 产能 29/832 | **51/832** | 原数字取自 `pkg-AutoInfo`（2026-10-26）。扫描器在 #638 前只认带时分秒的时间戳，漏掉 14 个真实产物；`docs/dev/coverage-baseline.md` 已明写该行"not reproducible from this tree" |
| 78 个必达域×源"零原始数据" | 78 是**必达总数**；其中 **14 个确有数据**，真正无数据 **64** 个 | `--evidence outputs` 对 source/KB 两段结构性失效（脚本自身已对此告警） |
| "A 类：源根本没配置" | **不存在**。78 个必达源 `configured=False` 计 **0** | 同上 |
| "39 个 KB 层级全部为空 / 资产账面为零" | **35/39 为空**；Raw 已有 **74** 条，Draft/Wiki 为 **0** | 同上 |
| "GFW 导致采集层天然折损严重" | 不成立。64 个无数据中 **59 个是"从未运行"**，只有 3 个 failing | 把"没跑"误读成"跑不通" |
| 预算告警"整条链路从未工作" | 缺陷真实，但漏了第二道阻塞（`AlertRule` 无 `cost_threshold` 字段） | 只看了 SQL，没看告警模型 |
| MCP 产品生成门禁"仍未 enforcing" | 门禁**在**（`output/__init__.py:2958/3649`）；真实的洞是 `user_id` 可选 | 与 founder-expectations 的过时措辞同源 |
| 提示注入"无任何 sanitize" | 有去标签层（`textutil.clean_feed_text`，4 个采集器调用）；无的是**指令隔离** | 把两件事合并成一件 |
| ruff 0.16.8 / 46 个待格式化 | pyproject 锁 **0.17.2**；`src/` 待格式化 **10** 个 | 沿用 9-17 旧值 |
| keystone "落后两个半月、分布不可信" | 头部 8-12、正文 9-13、**#657 已补"reconciliation"节**声明其为设计快照 | 未看当时已合并的修复 |
| brief v2/v3/v4 三版并存 | **已归档**（#657 把 v2/v3 移入 `docs/archive/`） | 同上 |
| bus factor 568/1,000 | **510/888**（非合并）；总提交 992 | 分子用了全部提交数、分母取整 |

---

## 一、这个项目是做什么的

AutoInfo 是一个**通用信息追踪与知识库平台**：用户配置信源（sources）和关注主题（topics），平台自动完成**采集 → LLM 结构化提取 → 质量门禁 → 四层知识库沉淀 → 信息产品生成 → 多渠道分发**的全链路。它的自我定位是"信息助理"——不是帮你搜索，而是把从采集到知识沉淀的体力活全部自动化。

按 `founder-expectations.md` 的定义，它不是开发者工具，而是**面向付费客户的商业化内容工厂**：RAW 产品（原始信息流、API feed、批量导出）与 PROCESSED 产品（简报、专题报告、教程、告警流）都是一等公民，平台是工厂，产品是商品。demo 域（21 个：medical-research、ai-commercial、语言学习族等）只是配置示例，领域本身不写在代码里。

当前规模（2026-10-29 首版；2026-10-30 在 HEAD `96f7fefe` 上复测，版本 v1.21.4）：

| 维度 | 数值 |
|---|---|
| 源码 | 174 个 Python 文件 / 95,192 行 |
| MCP 工具 | 149 个（35 类），dispatch 注册表已从 if/elif 链重构（#581） |
| CLI | 31 个命令组 |
| 采集器 | 30 个 handler（PubMed、SEC EDGAR、RSS、Web、Bilibili 等） |
| 测试 | 6,665 个用例 / 182 个验证场景（86 功能 + 96 回归） |
| 文档 | **总量不在此处写死**，以 `docs/dev/doc-inventory.md` 为唯一真值——本报告自身就在被统计范围内，任何一次文档增删都会让写死的数字失效（本次复核过程中它随文档增删变过三次，正好演示了这个脆弱点）。结构上含 **11 份 ADR**（`docs/adr/` 下另有 README.md 与 TEMPLATE.md，非 ADR）与 **12 份 spec** |
| demo 域 | 21 个，curated sources 总计 **154** 条（其中 `enabled: true` 110 / `enabled: false` 31 / 未显式声明 13） |

## 二、设计理念

1. **Agent-first（B1/B2/B3 三角色模型）**。系统的第一操作界面是 MCP 工具——149 个工具全部可被 AI agent 调用；CLI 只是人类的降级备选。人类"指挥者"（B3）用自然语言向 agent（B2）下达意图，agent 翻译成工具调用；"最终用户"（B1）只消费交付的产品。这是整个项目最根本的架构决策——连 AGENTS.md 本身都是写给 agent 的操作手册。

2. **领域无关**。加一个领域 = 加一份 `sources.yaml` 配置，不改代码。采集器通过 registry 查找（`collectors/registry.py`），加源 = 一个类 + 一次注册。

3. **产品优先 + 质量是硬约束**。质量门禁不是建议而是管道的一环：G0/G4 硬门禁（重试后阻断）、G1-G3/G5/G7 软门禁（可配置）、D1-D3 交付门禁；产品 QC 分三层（L0 确定性 gate → L1 可选 agent 语义评审 → ESCALATE 人类裁决），并明确"诚实的不确定（hedge）= 正确行为，不得标记"。

4. **KB 四层管道纪律**。01-Raw 是唯一入口（保证来源溯源完整），02-Draft 只能从 Raw 产生，03-Wiki 只增不删；Draft→Wiki 晋升是 **agent 操作、无人工闸**——因为 KB 被定义为"生产数据库"而非人工策展的知识库（2026-08-08 决策）。这条纪律有专门的验证场景（`director-backdoor.yaml`）锁住，不是纸面规定。

5. **BYOK + LLM 治理**。用户自带 key，平台只存 `${ENV}` 引用从不落原始密钥；所有 LLM 调用路径统一走 `call_with_fallback`（主模型 + fallback 链 + per-provider 信号量限流 + 429/5xx 抖动退避）；判断类调用（G4/G5/llm_judge）走 **config-first 三级链**：`llm.judgment_model` → `llm.model` → 抛 `JudgmentModelNotConfiguredError`（`config.py:1531 resolve_judgment_model`，issue #195 于 2026-09-03 废止了原先的 `JUDGMENT_MODEL` 代码常量）。因此判断类调用既不会随 `llm.tasks` 漂移，也不会在未配置时静默猜测。

6. **诚实工程（这是本项目最有辨识度的理念）**。"新问题无穷"的焦虑被制度化为三份登记：`tests/TRIAGE.md`（已知红灯预算，按测试 ID 锁定身份而非数量）、`docs/known-limitations/demo-quality-residuals.md`（产品质量残差登记：现象→类→检测层→严重度→状态）、gap register（带独立评审回执）。验证场景在环境缺依赖时报 `unconfigured` 而非静默通过；文档数字由 `doc_inventory --check` + guard.yml 防漂移；"登记在先、修复在后"是明确的流程要求。

7. **知识即资产**。实时 feed 是流量，积累的知识库才是长期资产——这句理念在第四节的问题分析里会被反复对照。

## 三、9-17 报告 P0 项的落地核实（本轮实测）

上一份健康度评估的同日修复声称解决了 5 项 P0/P1。本轮逐项验证，**全部属实**：

| 9-17 报告的问题 | 本轮实测结果 |
|---|---|
| `mcp/server.py` 11,863 行上帝模块 | **已拆分**：现为 1,147 行 hub（注册表 + 调度），handler 按 domain 拆到 `mcp/tools/`（#581） |
| `output/__init__.py` 9,336 行 | **已部分拆分**：现为 5,261 行（export/ebook/video/audio 等已独立成模块） |
| 6,905 个运行时产物被 git 跟踪 | **已清**：当前跟踪 1,092 个文件，`knowledge/collections/outputs/...` 命中 **0** |
| release-please 断线（当时停在 1.11.0） | **已恢复且运转正常**：现在 1.21.4，release PR 自动合并工作流在位（8 条 workflow） |
| mypy strict 192 错 / ruff 版本漂移 / 红灯预算只锁数量 | **已修**：mypy 全树 0 错（174 文件）、ruff 锁定 **0.17.2**（9-17 时的 0.16.8 已在 #492/#619 递增）、TRIAGE 预算已改为测试 ID 身份锁且 2026-10-12 起预算清零 |

工程卫生债在六周内被实质性清偿，这一点应当先于问题清单被承认。但清偿的是"机制层"的问题——下面是**当前**的问题。

---

## 四、当前问题分析

### P0（最核心）：机制规模与实际产出严重失衡——工厂建好了，订单没有流动

**先修正口径**：本报告初版直接引用了 `pkg-AutoInfo/README.md`（2026-10-26）的 29/322/481，并据此推出"78 个源零数据""39 个 KB 层级全空""资产账面为零"。复核发现这三个数字都来自一次**已知失效的测量**——`coverage_matrix.py --evidence outputs` 对 source 与 KB 两段是结构性失效的（脚本自身现在就会对此打印警告，`docs/dev/coverage-baseline.md` 亦白纸黑字写明 pkg 那一行"is not reproducible from this tree"）。下面全部替换为 2026-10-30 在本树上的实测值。

**当前实测（`coverage_matrix.py --evidence .`，HEAD `96f7fefe`）**：

| 生产能力矩阵（13 域 × 8 产品 × 8 格式 = 832 格） | 数量 |
|---|---|
| 有真实产物的格 | **51** |
| 空 gap（待补） | **164** |
| 未配置（LLM 门控，无 key） | **136** |
| 组合不成立（N/A） | 481 |

对比 pkg 的 29/322：差距全部来自 #638（2026-10-27）修的扫描器缺陷——旧正则只接受带时分秒的时间戳，把 `validation_delivery` 与早期 MCP 产出物（纯 `YYYYmmdd`）判为非产物，一次就漏掉 14 个真实 cell。

非矩阵维度（同样重新实测）：

- **78 个"必达域×源"组合中，64 个无原始数据**（不是 78）。而且**成因不是反爬**：`scripts/source_diagnosis.py` 把 78 条分成 `satisfied 9 / degraded 5 / failing 3 / never-attempted 59 / configured-off 2`，即 **59 条是"配置好了但从未运行过"**，只有 3 条是真 failing。`configured=False` 的条数为 **0**——不存在"源根本没配置（A 类）"这一说，78 个必达源全部已配置。另外 14 个组合确有数据（pubmed 29 / techcrunch 33 / producthunt 33 / 36kr 30 / project-gutenberg 33 / commonlit 28 / news-in-levels 23 / arXiv 21 / Stack Exchange 16 / HackerNews 11 / Crunchbase 10 / Substack 5 / seeking-alpha 4 / cnbc 4）。
- **39 个 KB 层级中 35 个为空**（不是 39）。`01-Raw` 已沉淀 **74 条**（medical-research 39 / language-learning 26 / ai-commercial 5 / financial-news 4），`02-Draft` 与 `03-Wiki` 各 **0** 条。"知识即资产"的资产不是零，而是**卡在 Raw 层**：有原料、无加工、无成品。
- 14 个交付渠道、15 个能力**没有 per-adapter 的可执行场景**（矩阵的文本启发式只能匹配到 3 个渠道 + 1 个能力；实测 `discord/telegram/wechat_work/wechat_oa/dingtalk/feishu/rest_api` 在场景库中 grep 全为 0）。

残差登记表里的两条近期记录把这条主线串成了因果链：ai-commercial 域仅有 5 条 KB 条目建于 2026-08-15，T11 采集到的 58 条新材料**卡在 gitignored 的 `collections/` 里无法入库**（缺 `AUTOINFO_LLM_API_KEY`，process 层跑不了），于是 7 个 digest 单元因"所有候选条目过期"被新鲜度闸门拒产。采集→处理→知识库→产品这条主干道，目前每一环都有数据流动的瓶颈。

两个旁证说明这不是纸面推断：其一，最近两次发版（1.21.3/1.21.4，10 月下旬）都在修 process 层的真实生产 bug——处理游标按 item id 单调推进（#637）、`--since-days/--newest-first` 让预算内的运行能触及新条目（#655）——说明生产运行真的在跑，且跑的时候暴露的都是"新内容到不了 KB"这一类洞；其二，154 条 curated source 中 **31 条 `enabled: false`**（GFW-blocked / dead / 404），真实的网络折损存在，但**它不是 78 个必达组合无数据的主因**（主因是 59 条从未运行）。

**一句话判断（数字已修正）：项目用六周把"工程机制"做到了中大型开源项目水准（149 工具、6,665 测试、182 场景、近 4 万行文档），但"工厂产能"只兑现了 51/832，且 KB 的 Draft/Wiki 两层完全空白——下一步的主要矛盾不在代码质量，而在让数据流过管道。** 值得注意的是，修正后的画像比初版**更可行动**：问题不是"外部环境把采集打死了"（那只剩修反爬一条路），而是"大部分管道从来没被跑过"——59/78 从未运行、Raw→Draft 的晋升一次都没发生。`pkg-AutoInfo` 交付包给出的路线（T1 采集源诊断 → T2 分四批补格 → T3 KB 层级 → T4 场景库）方向正确，且把"每域至少 2 个稳定源"设为硬指标而非"78 全绿"，这个取舍依然是对的。

小瑕疵：该交付包引用的命令 `python -m autoinfo.cli gap` **并不存在**（`docs/dev/source-diagnosis.md` 已注明其被 `scripts/source_diagnosis.py` 取代）——三天前生成的交付包就已经和仓库有轻微漂移，这正好复现了残差登记表 C 节"文档与代码无对账"的那一类问题，只不过这次发生在交付包里。

### P1：已登记、至今未修的真实缺陷

1. **`src/autoinfo/cost.py:818` 双 WHERE SQL 缺陷**（2026-09-17 登记，至今未修）。`f"SELECT DISTINCT domain FROM cost_log{where} WHERE domain != ''"` 在 `where` 已含条件时拼出第二个 WHERE，`period="today|week|month"` 一律抛 `sqlite3.OperationalError`，被外层 `except Exception: pass` 吞掉。实测复现（给 `list_alert_rules` 打桩返回一条带 `cost_threshold` 的规则）：

   ```
   today 0    week 0    month 0    all 1      ← 只有 where 为空时能走通
   ```

   **但这一条完整的诊断比初版写的更长**：即使把双 WHERE 修掉，`budget_status` 仍然会是空的。原因是 `AlertRule`（`models.py:168`）**没有 `cost_threshold` 字段**——它的 `kind` 只有 `content` 与 `source_credential_missing` 两种，所以 `getattr(alert, "cost_threshold", None)` 恒为 None，随后的 `if threshold is None: continue` 直接把每条规则跳过。`cost.py:808-816` 的注释自己也承认了这一点（"Wiring it up needs a cost-budget rule kind, not just this import fix"）。初版说"修法已在 TRIAGE 写明，是个小改动"——那个改动**不足以让告警生效**，真正的修法是两步：修 SQL + 给 `AlertRule` 增加 cost-budget kind。

   同时也要修正"整条链路从未工作"这个判断：`get_budget_thresholds` MCP 工具走的是 `get_report()`（默认 `period="all"`），实测**可用**（`current_spend=39.15`，`threshold_status` 正常返回）。死的不是整个成本治理，而是 `cost_dashboard(period≠all)` 这一条路径，以及**从未被任何地方调用**的 `evaluate_budget_alerts()`（全仓 grep：除自身定义与文档字符串外 0 调用点）。
2. **并发 outbox 写丢通知**（TRIAGE 2026-09-17 观察项）。16 线程并发写时 `1 of 16 events dropped`，且**明显诊断已被证伪**——`busy_timeout` 自 8 月 28 日起就在 WAL 之前设置，失败仍发生在 WAL 语句上，根因未定性。这是一条**真实的产品侧数据丢失路径**（丢的是最终用户的通知行），不是测试问题。需要专门的 16 线程复现来定性，一直以"负载敏感 flake"的身份挂着。
3. **`test_batch_size_passed_to_run_processing` 已修**（初版记为"至今在案"，实际报告同日的 #655 已连断言一起修好；单跑 `2 passed in 2.67s`）。仍成立的只剩后半：`test_generate_report_json_format` 依赖本地数据 + LLM key，属非封闭测试——但初版"烧 230 秒被 180s 杀死"在当前树**不复现**（本轮单跑 25–30s 通过，失败时会降级而非超时）。**"没有任何东西盯着 canonical selection 之外的目录"这一条仍然成立**，是四个 P1 里唯一没有改善的。
4. **`link_items` 不校验 relation type**（founder-expectations §14 自认的 v1.6+ 唯一残留）：`RelationType` 枚举存在但写路径放行任意字符串（`kb.py:1095`，直接 `INSERT` 进 `relations`），低工作量，从 8 月挂到现在。

### P2：商业化路径上的架构性阻塞

1. **REST API 无鉴权**（本轮 grep 确认 `api/server.py` 对 `auth|api_key|token|bearer` **0 命中**）。该文件唯一的"鉴权"是 Stripe 回调的 `STRIPE_WEBHOOK_SECRET` 签名校验，不覆盖任何业务路由。README 靠"默认绑 127.0.0.1"兜底，但平台的商业模型是 B1 付费客户通过渠道和门户消费——当前架构**无法安全对外托管**。
2. **多租户未实现**：`MultiUserConfig.enabled=False`，没有 auth/teams/RBAC。**修正一处标记错误**：初版说"B1 的 KB 租户隔离在 cross-dimensional-catalog 里是 🔴"，实测该矩阵 A3×B1.2 单元格是 **🟡**（"KB is usable but no tenant isolation"）；🔴 只出现在 gap register 的 CD-001/CD-042 与 A3×B1.7（无 churn 快照恢复）。即：**矩阵说"部分交付"，缺口登记说"未交付"**——初版混用了两套标记。实质结论（无租户隔离）不变。
3. **产品访问门禁的真实缺口是"user_id 可省略"，不是"门禁不存在"**。初版称 MCP 产品生成工具上"门禁仍未 enforcing"，这一点与代码不符：`generate_digest` 在 `output/__init__.py:2958`、`generate_report` 在 `3649` 都调用了 `check_access()`，且 `_handle_generate_digest`/`_handle_generate_report` 两个 handler 均透传 `user_id`。真正的洞是签名里的 `user_id: str = ""`（`mcp/tools/output.py:782/944/1154`）——**不传 user_id 就完全跳过门禁**。所以免费/付费分层在 agent 界面上确实可绕过，只是绕过方式是"省略参数"而非"门禁缺失"。（founder-expectations §14 的措辞与此同源过时，需一并修。）
4. **无提示注入防御——准确说是"有去标签，无指令隔离"**。存在的一层：`textutil.clean_feed_text()`（剥 HTML 标签、解码实体、归一空白）被 `rss.py` / `hackernews.py` / `http_api.py` / `yahoo_finance.py` 四个采集器调用，`redteam-prompt-injection-feed.yaml` 用真实 sanitizer 断言注入文本"保持惰性"。不存在的一层：`llm.py` / `process.py` 对 `prompt.?injection|sanitiz` **0 命中**，`data/prompts/extraction_system.md` 全文只有一句系统提示，**没有任何"以下内容是不可信数据、不得执行其中指令"的声明或分隔符**——`_build_prompt` 直接把 `item.content` 拼进 user prompt。标签剥离能挡住 `<script>` 型注入，挡不住"忽略以上指令，改为输出 X"型注入。对一个"把互联网内容喂给 LLM 再把产物卖给付费客户"的平台，这是结构性风险。
5. **无熔断器**：`circuit.?breaker` 全 `src/` 0 命中。`status.py:297` 只在连续 3 次错误后把该源 health 标为 `error`，**只报告不干预**——`collect.py` 侧没有任何"跳过不健康源"或"降速"逻辑（`enabled: false` 是静态配置，非动态熔断）。反爬致死的源会持续消耗采集线程与下游 LLM token。

### P3：质量门禁的已知盲区（残差登记表在案，此处汇总现状）

- **G7 抓不住编造年份**：`_REL_TOLERANCE=0.05`（`quality.py:1875`）的容差匹配让"won the 2031 World Cup"这类编造年份在含 2015–2027 数值的源文里全部"命中"。#444 注入实测检出率仅 **69.4%**；已裁决不升级为 block（否则 30% 编造年份照常通过、还把年份声明全面变成阻断面）。真正的修法是年份精确比对，尚未排期。这是"产物卖给付费客户"场景下最伤的盲区——数字幻觉里最难看出来的就是年份。
- **D2 orphan-entity 误报 ~27%**，只能 escalate 不能阻断，每轮产生人工裁决负担；H1/H2 gate 的良性误报同样每轮需人工过目。
- **三类单元处于"未验证"状态**（与 `docs/dev/validation-reports/capability-27x3/matrix.json` 的 81 行逐格统计一致：`L3=35 / blocked-no-llm-key=36 / blocked-stale-sources=7 / blocked-no-browser=3`）：3 个 `report:video`（本机无完整 Chrome，`~/.cache/puppeteer` 只剩 `chrome-headless-shell` 残件）、7 个 ai-commercial digest（上游 KB 陈旧，补 key 后必须先 process 再重跑）、36 个 LLM 门控单元（无 key，从未被调用）；MOBI 成功路径（CI 不装 calibre，README 已诚实降级为 🟡）。

### P4：工程流程与文档债

1. **双 agent 并行写 + release PR 自动合并的持续摩擦**：AGENTS.md 自己承认每次合并前必须 rebase 到最新 main（否则 ruleset 直接拒绝），而 release PR 在 main 上的每次 push 后数分钟内自动合并、使所有 open PR 的基线失效——预算"~20 分钟完整 CI 周期"。官方缓解手段是"更少更大的 PR"，这与"大 PR 高风险"存在张力，是制度性成本而非一次性成本。
2. **全量测试 55 分钟**（9-17 实测值，本轮未重跑全量，不确认也不否定）；但初版"CI 只能跑快子集"**不成立**：`ci.yml:241` 实际跑的是 `pytest -m "not real_api" -q`，而全仓只有 `tests/integration/test_real_api.py` 一个模块被打 `real_api` 标记（3 个用例）——实测 `--collect-only -m "not real_api"` = **6662 / 6665 collected（3 deselected）**。`test` 作业名里的 "fast subset" 只是历史命名，Nightly 另有每日 02:00 的完整顺序跑。真正的负载敏感 flake（EPUB 边界、16 线程 outbox）在机器繁忙时仍会伪装成回归。
3. **keystone 文档滞后——但已被 #657 部分处理**。头部 `Last updated: 2026-08-12` 与正文 2026-09-13 自相矛盾（初版据此说"两个半月"，实际是文档头未更新、正文更新过）。更重要的是 #657（2026-10-30）新增了 "Reconciliation — This Catalog vs. `pkg-AutoInfo` Production Evidence" 一节，**明确声明 126 格状态是 2026-08-12/09-13 的设计评审快照、不是当前生产真值**，并给出"哪个问题查哪份文档"的对照表。所以"🟢/🟡/🔴 分布已经不可信"这个判断现在有了官方背书，但**"没有任何声明"这个隐含批评已过时**。残留问题只剩：头部日期未同步、126 格状态本身仍未重新推导。
4. **文档体量与版本堆积**：文档总量见 `doc-inventory.md`；brief 三版并存的问题**已解决**——#657 把 v2、v3 与旧版 `AutoInfo开发简报.md` 移入 `docs/archive/`，`docs/dev/AutoInfo-development-brief-v4.md` 成为唯一活文档（实测 `find docs -iname "*development-brief*"` 只剩 3 个文件，其中 2 个在 archive）。对新人（和 agent）的检索成本仍在上升，但这一条具体债已清。
5. **`ruff format` 无 CI 门禁**：仍在。但存量数量要修正——`ruff format --check src/` 现在是 **10 个**（不是 46；46 是 9-17 的中间值，此后 #492/#597/#609/#619 又清了一批），全仓 `--check .` 为 120 个。CI 无 format 步骤，pre-commit 的 `ruff-format` 只处理被暂存文件，任何人触碰这些文件都会带出整文件重排的噪音 diff。

### P5：治理风险

- **bus factor ≈ 1**：全仓 992 次提交中 `renanzai`(524) + `renanzai40`(44) = 568 条来自同一人（两个账号），`1StepMore`(245) 与 `Hermes Agent`(78) 是 agent/组织账号，`github-actions[bot]`(90) + `dependabot[bot]`(10) 是机器人。口径需说明：初版把 568 放在"非合并提交"句子里，实际 **524/44 是含合并的全量计数**；非合并口径下为 `renanzai 501 + renanzai40 9 = 510 / 888`（1StepMore 201、Hermes Agent 76、bot 100）。无论哪个口径，**实质性人类贡献者都是 1–2 人**，结论不变。项目的方法论文档化程度很高（这是对冲），但"两个 agent 写同一个仓库"的流程本身依赖唯一的人类指挥者持续在线。
- 工作区当前的未跟踪产物（`pkg-AutoInfo/`、`pkg-AutoInfo.zip`）尚无归属约定——它既不是 `.omo/` 那样的已定义运行时空间，也没进 git；按残差登记表的纪律，这类"新生表面"应当先登记归属再膨胀。**佐证**：#657 在 catalog 里描述 pkg 时写的是 "not tracked in this repo — reproduce with the command in the last column"，即项目已经承认它的临时性，但尚未给出归属约定。

---

## 五、值得肯定的部分（避免失衡的画像）

- **诚实机制是同类项目少见的**：残差登记表、TRIAGE 身份锁、`unconfigured ≠ pass`、防漂移门禁、"登记在先修复在后"，构成了一套把未知逐步变成已知的制度，且本轮核实显示这些制度**真的在被执行**（预算清零、P0 清偿都有证据链）。
- **9-17 评估的修复质量高**：mypy 清偿不是逐条 suppress 而是按根因批量复位，过程中还挖出 6 个被 mock 掩盖的真实运行时缺陷并修复——这种"修债修出真 bug"的路径说明团队对债的态度是认真的。
- **发布自动化已闭环**：release-please + 自动合并工作流运转正常，版本真值清晰。

## 六、总体判断与建议方向

**总体判断（数字已修正）**：AutoInfo 的工程机制成熟度已经明显高于它的实际产能。六周前的主要矛盾（工程卫生、上帝模块、发布断线、红灯预算）已被有效清偿；当前的主要矛盾是**"从会跑的工厂到有产出的工厂"**——832 格里 **51** 格的产能、`02-Draft`/`03-Wiki` 两层完全空白、64 个必达源组合无数据（其中 59 个从未运行），才是"知识即资产"这个故事能否成立的唯一判据。同时有一条必须点名的暗线：**预算告警的 dashboard 路径死亡（cost.py 双 WHERE + `AlertRule` 缺 cost-budget kind）+ REST 无鉴权 + 提示注入无指令隔离**三者共同意味着，这个定位"付费客户平台"的系统，当前在"收钱、看住钱、安全地处理外部内容"三个环节都还是开发机姿态。

**建议优先级**（与 `pkg-AutoInfo` 交付包的 T1-T4 路线不冲突，是补充）：

1. **按交付包执行生产补齐**，但把 T1 的诊断口径改对：先跑 `scripts/source_diagnosis.py`（不是交付包里那个不存在的 `autoinfo gap`），因为 **59/78 是"从未运行"而非"跑不通"**——先跑一遍比先修反爬的性价比高一个数量级。
2. **修 `cost.py:818` 时一并补 `AlertRule` 的 cost-budget kind**（两步，不是一步）。只修 SQL 会让 `budget_status` 依然为空，TRIAGE 里那条"一行改动"的写法是错的。
3. **为 outbox 并发丢通知立 16 线程复现**（TRIAGE 自己的要求）：生产补齐后通知量会上升，这条数据丢失路径从"负载下偶发"变成"必然暴露"。
4. **在对外托管 / 首个真实付费用户之前**：REST 鉴权 + 把 `generate_digest`/`generate_report` 的 `user_id` 从可选改为必填（门禁本身已存在，是可绕过而非缺失）+ 提示输入的指令隔离层（不是标签剥离——那层已有），三件至少要有最小版本。
5. **刷新 keystone 矩阵**：#657 已经承认 126 格是设计快照；下一步是真正重新推导（或明确废弃该矩阵、只留 `coverage_matrix.py` 的实测口径），并同步文件头部的 "Last updated"。
6. G7 年份精确比对进入排期（残差登记已给出方案：年份不做容差、与来源年份集合等值判定），排在"产物开始交付给真实用户"之前即可。

---

## 附：本报告的证据清单

> 全部数字于 **2026-10-30** 在 HEAD `96f7fefe`（v1.21.4）上重跑复算。命令附在每行，可独立复现。

| 结论 | 证据 / 复现命令 |
|---|---|
| 规模：174 py / 95,192 行 | `find src -name '*.py' \| wc -l`；`find src -name '*.py' -print0 \| xargs -0 cat \| wc -l` |
| 149 MCP 工具 / 35 类 | `_TOOL_DISPATCH` 正则计数 149；README 表格 category 行 35 |
| 31 CLI 组 / 30 采集 handler / 182 场景（86+96） | `grep -c "add_typer(" cli/__init__.py`；排除 5 个非 handler 类后 30；`regression: true` 96 + 其余 86 |
| 测试 6,665 | `pytest --collect-only -q` → `6665 tests collected in 30.68s` |
| 文档总量 | `python3 scripts/doc_inventory.py --check` → 头部 `Total files`（**不写死**：本报告自身也在统计范围内） |
| god module 已拆分 | `wc -l`：server.py **1,147** / output/__init__.py **5,261** |
| 运行时产物已出跟踪 | `git ls-files \| wc -l` = **1,092**，`grep -cE '^(knowledge\|collections\|outputs\|logs\|mvp)/'` = **0** |
| mypy 全树 0 错 | `.venv/bin/mypy src/` → `Success: no issues found in 174 source files` |
| ruff 锁定 0.17.2 | `grep ruff== pyproject.toml` → line 91；CI 注释/pre-commit 为 0.17.1 |
| ruff format 存量 10（src） | `.venv/bin/ruff format --check src/` → `10 files would be reformatted, 180 already formatted` |
| 产能 51/164/136/481 | `python3 scripts/coverage_matrix.py --evidence .`（`--evidence outputs` 同为 51/164/136/481，但 source/KB 两段失效） |
| 78 必达源：14 有数据 / 64 无 | `.venv/bin/python scripts/source_diagnosis.py` → `satisfied 9 / degraded 5 / failing 3 / never-attempted 59 / configured-off 2`；`collections_items>0` 计 14；`configured=False` 计 **0** |
| KB：35/39 空，Raw 74 / Draft 0 / Wiki 0 | 按 `end-user-matrix.yaml` 的 13 域遍历 `knowledge/<d>/{01-Raw,02-Draft,03-Wiki}` |
| cost.py 缺陷仍在（双 WHERE） | `src/autoinfo/cost.py:818`；复现：`period=today/week/month → budget_status 长度 0，all → 1` |
| cost.py 第二道阻塞 | `AlertRule`（`models.py:168`）无 `cost_threshold`；`getattr(...)` 恒 None |
| `evaluate_budget_alerts()` 无调用点 | 全仓 grep（排除定义行）0 命中 |
| `get_budget_thresholds` 可用 | 实测 `current_spend=39.15448075`，4 条 threshold_status |
| REST 无鉴权 | grep `auth\|api_key\|token\|bearer` 于 `api/server.py` → **0**（仅 `STRIPE_WEBHOOK_SECRET` 签名校验） |
| 多租户未实现 | `MultiUserConfig.enabled = False`（`config.py:551`） |
| 门禁存在但 user_id 可省 | `output/__init__.py:2958`(digest) / `3649`(report) 调 `check_access`；`mcp/tools/output.py:782/944/1154` 签名 `user_id: str = ""` |
| 无熔断器 | grep `circuit.?breaker` 于 `src/` → 0；`status.py:297` 仅标记 health |
| 有去标签、无指令隔离 | `textutil.clean_feed_text`（rss/hackernews/http_api/yahoo_finance 4 处调用）；`llm.py`/`process.py` grep sanitize → 0；`extraction_system.md` 仅 1 行且无 untrusted 声明 |
| G7 容差 0.05 / 检出率 69.4% | `quality.py:1875`；残差登记 #444 行 |
| D2 orphan ~27% | 残差登记第 14 行 |
| 未验证单元 3/7/36 | `capability-27x3/matrix.json` → `L3=35, blocked-no-llm-key=36, blocked-stale-sources=7, blocked-no-browser=3` |
| kb.py 静默吞异常 25 处 | `grep -c "except Exception:" src/autoinfo/kb.py`（9-17 时 21 处，**回升**） |
| 发布正常 | `git log --grep="chore(main): release"` → 1.20.0→1.21.4 连续；8 条 workflow |
| bus factor | 全量 992 提交：renanzai 524 + renanzai40 44；非合并 888：501+9 |
| brief 已归档 | `find docs -iname "*development-brief*"` → archive/v2, archive/v3, dev/v4 |
| keystone 已声明为快照 | `cross-dimensional-catalog.md` #657 新增 "Reconciliation" 节 |
| 交付包命令漂移 | `python -m autoinfo.cli gap` → `No such command 'gap'`；`docs/dev/source-diagnosis.md:15-22` 记载 |
