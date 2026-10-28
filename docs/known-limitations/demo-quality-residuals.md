# Demo 包质量残余风险登记表

> 目的:把"每次跑都能发现新问题"的焦虑变成可枚举、可检测、可裁决的**已知残余**。
> 原则:内容生成产品不存在"零问题"状态;生产级 = 残余可列举 + 每类有检测层 + 检测有界。
> 用法:每轮 review/单次生产暴露**新类**时,先登记到此表(现象 → 类 → 层 → 严重度),再决定是否修复。

## A. 语义残余类(LLM 随机性,无法确定性根除,靠检测+裁决)

| 类 | 典型表现 | 检测层 | 严重度 | 状态 |
|---|---|---|---|---|
| 叙事↔来源漂移 | 源信号被改名/抽象成新词("low VIX/inflation/AI spending" → "market breadth") | H1 gate(已知形态)+ L1 battery + 外部 review | P1(若混入) | 有约束+检测;新形态靠 battery/review |
| 推断措辞无 hedge | editorial 句断言市场方向/动机("the smart money is betting") | L1 battery(#191 只约束 feature_story,未盖 editorial 开场)+ 审查程序 | P2/P3 | **已登记(R6/R7 连续双样本再现);审查程序已入 skill demo-package-deliverable-review(2026-09-03);prompt 层约束已补(#210: EDITORIAL_OPENING_HEDGE_CONSTRAINT 覆盖 Editor's Note / Executive Summary / column Deep Dive 开场)** |
| 实体事实误差 | 与来源不符的数字/事实(非汇率类) | G7 确定性 gate(数字+实体可溯源,默认 soft/flag);L1 battery 部分;外部 review | P1(若混入) | 已有确定性层;默认仅标记不阻断,可按域升为 block |
| 产物自述与正文不符 | Executive Summary 称 "2 selected items",正文只渲染 1 条;narrative 命名正文从未出现的实体 | D2 self-count(**hard block**,#445,0 误报 / 222 个真实产物)+ D2 orphan-entity(flag/escalate,#445,实测 ~27% 误报率故不阻断)+ L1 battery | P1 | 计数类已确定性防死;实体类只升级不阻断,**新形态靠 battery/review** |
| 实体候选抽取噪声 | `_entity_claims` 把冠词吞进实体("An AI-based");把普通动词/句首普通名词当实体("Use"/"Remove"/"Presence"/"Base"/"Data"/"Development");列表项上下文里句首判定失效 | 无(抽取层自身无 gate;只表现为 orphan-entity 信号变噪) | P2 | **已登记并已修(2026-10-04,#449 测量副产物)**:三处根因分别修复(多 token run 剥冠词、停用词表补常见词、markdown 列表/引用/加粗前缀纳入句首判定);medical-research 的 orphan 触发率 26.6% → 20.1%,其余域不变(其候选非英文,英文停用词覆盖不到)。因 orphan-entity 已是 escalate-only,全程无阻断影响。连字符形容词("AI-based")为刻意保留:加规则会误伤 Wi-Fi / Spider-Man 类真实实体 |
| 年份粒度被容差匹配吸收 | 声明 "won the 2031 World Cup"/"expand by 2047" 这类编造年份:`_no_year_hallucination` 因命名形状豁免而放行;G7 也放行——`_REL_TOLERANCE=0.05`,源文里任一落在 5% 内的数值即算"已支撑"(实测源文含 2027/1974/2015/2020/2022,全部落在 2047 的 5% 内,`_value_matches_source(2047)` 返回 True) | 无。G7 的数值匹配是**容差**匹配,不具备年份粒度;`_no_year_hallucination` 的命名豁免只认形状 | P2 | **已登记并已否决"年份范围 block"方案(2026-10-05,#444 残留)**:注入 216 个编造年份实测检出率仅 69.4%,漏检 66 个;真实数据侧 17 个年份声明 0 误报,但**灵敏度不足才是决定因素**——把 G7 改为 block 会让 30% 的编造年份照常通过,同时把年份类声明变成阻断面。要真正关闭需**精确年份比对**(年份不做容差,与来源年份集合做等值判定),而非调阈值;在此之前保持 G7 flag 不阻断 |
| 主题归类/结构组织 | funding 表漏放头条条目(VAST)→ Additional Topics | 无(L0/L1 均不判组织) | P3 | 非缺陷,润色建议 |
| 金额换算轻微漂移 | 新中文金额形态(数百万/几千万/千万级)未注入,LLM 自算 | G6 抓量级错(隐含汇率越界);抓不住轻微漂移 | P2 | 已覆盖数字+中文数字形态;新形态靠 G6 部分兜底 |

## B. 确定性层(已防死或必抓,列出以证明覆盖)

| 类 | 机制 | 类型 |
|---|---|---|
| 词级截断 | `_truncate_ellipsis` + H2 | 防 + 抓 |
| 列表粘连 | 模板 trim_blocks 修复 + H3 | 防 + 抓 |
| 占位/空壳/日志泄漏 | F1-F4 / C2 / C3 | 抓 |
| USD 汇率(数字+中文数字) | `_annotate_rmb_usd` + `_RMB_TEXTUAL_RE` + G6 | 防 + 抓 |
| 404 URL 伪造 | prompt 逐字约束 + `_sanitize_report_urls` | 防(结构上不进产物) |
| 假条目/引用完整性/长文 grounding | C1 / C5 / C6 | 抓 |
| 自述计数与渲染不符 | `self_claims.self_count_contradictions` + D2 block(#445) | 抓 |
| 合成引用错配/命名未被来源提及的实体 | `SYNTHESIS_ENTITY_GROUNDING_CONSTRAINT` + `_ground_synthesis_citations`(#445) | 防 + 抓 |
| 空段渲染孤儿标题 / magazine 空 label | column/report/tutorial 空段跳过 + magazine-digest label 兜底(#445) | 防 |

## C. 工具层残余(影响检测能力,非内容缺陷)

| 类 | 表现 | 影响 |
|---|---|---|
| battery LLM 格式失败 | **已加固（#battery-verdict-parse，2026-09-29）**：此前部署跑 ~13/40 条目误报 "no parseable verdict block"，根因是 5 因叠加——repr 陷阱（list/None content 被字符串化）、解析器过严（只认 `## Verdict` + 小写加粗键）、JSON 路径从未真正传 `json_mode=True`、截断不可见（finish_reason=length 被当乱码）、空字段正则吞下一行（把相邻 note 当 evidence）。现解析器容忍 `#`/`###`/加粗标题与全角冒号漂移，空字段同行为空即整块丢弃，截断显式标注，JSON 路径真正请求 json_mode 并用宽容解析，外加一次格式修复重试 | L1 覆盖恢复；**不可达或修复后仍不可解析的输出依旧 ESCALATE——这是有意的 fail-loud，不是缺陷**；markdown 表格形态仍不解析（丢弃→ESCALATE），需要时另登记 |
| gate 良性误报 | H1 常见词(month/backing)、H2 源标签(npr-news)、包根 C3 | 每次需人工裁决;是保守设计不是 bug |
| presentation LLM 合成失败 | 连续空 slides → KB-derived 兜底(确定性输出) | 产物有效但非 LLM 合成;#220 已知;**#646 起该类降级可被观测**:生成层记录 provenance(`llm_provenance()`),能力矩阵对 KB 兜底产物只报 `L2-degraded`,不再谎报 L3 |
| **测试 fixture 日期字面量过期(时间炸弹)** | **已登记并已修(2026-10-12,#506/#509)**:测试 fixture 把 `collected_at` 写死成绝对日期,而 domain freshness 阈值随日历推移——2026-08-17/08-25 的 fixture 在 2026-10-09 还是绿的,10-11 集体越过阈值,`generate_digest`/`generate_tutorial` 抛 `StaleSourceError`,**13 个失败看起来与触发它的改动毫无关系**。这不是 13 个 bug,是 1 个 bug 穿了 13 件外套;审计后发现暴露面是 **60 处字面量 / 24 个文件**,只是各自 domain TTL 长才暂时没爆 | 根治:新增 `tests/_freshness.py`(`_NOW` 冻结于 import,保证同 offset 两次调用字节相同)+ `tests/validation/test_freshness_guards.py`(未来 30 天～过去 90 天窗口内出现日期字面量即 fail,含 3 个自检用例防守卫空转)。**新守卫有约 3 个月提前量,到期后新字面量会被自动拦下**;日期若本意"陈旧"则保持字面量——它只会越来越旧,永不过期 |
| **文档数字与代码之间无对账(闭环缺口)** | **已登记并已修(2026-10-12,#508 + 本次补断言)**:CLI 命令组数曾被写成 32,而 Typer `registered_groups`(`add_typer` 集合)实际是 31——`init` 用 `app.command()` 挂载,不算 group。**它在 main 上无限期待着,一次红都没产生**,因为 `doc_inventory.py --check` 只比 README↔AGENTS↔SKILL(一致性校验),而 `build_release_check.py` 只**报出**代码值、从不与文档比对。两个门禁各管一半,中间那道缝没人看 | 已补 `build_release_check` 的 `documented CLI group count matches autoinfo.cli` 断言(文档声明值 == `len(app.registered_groups)`),并用 2 个测试锁住(含伪造数字必须变红的负向用例)。**教训可推广:一致性校验 ≠ 真实性校验,凡是"文档里的数字"都需要一条对代码的断言**;README 枚举还长期漏了 `validate` 而多列 `init`,同样是靠这条断言才暴露 |

| **CI 选择集内测试打公网(非 hermetic)** | `tests/mcp/test_validation_tools.py::TestRunScenarioCliHttp` 的 `test_http_success` / `test_http_json_assert` 直接 GET `https://example.com` 与 `https://jsonplaceholder.typicode.com/todos/1`。`_run_http_step` "永不 mock" 是**有意的正确契约**(要真 HTTP 语义、真status code、真 JSON body),错的不是它,而是**测试把目标指向公网而非本地**。网络受限 / DNS 慢 / 对端抖动时,失败形态不是一条断言失败,而是 `pytest-timeout` **180s 挂死**(实测 SSL `do_handshake` 停滞),报错完全指向别处 | 同 #506 时间炸弹的一类:与被测代码无关的失败伪装成回归,直接烧掉一次"必须状态检查"。且它让 `tests/TRIAGE.md` 的 known-red 基线无法覆盖这类不确定失败。**已处置(2026-10-12,#519/#521)**:改为进程内 `ThreadingHTTPServer(("127.0.0.1", 0), ...)` 提供同一份 body/status/JSON 形状(沿用同文件 `test_http_slow_drip_request_aborted_on_timeout` 的既有写法),`_run_http_step` 的"真请求"契约一字未动——变的只是 URL 指向 |
| **tests/ 下混入非测试脚本** | `tests/run_q2b_collector_tests.py` 是独立脚本(结尾 `sys.exit(0)`),不是 pytest 测试。默认 `python_files = test_*.py` 不收集它,所以流水线无恙;但任何人显式把路径喂给 pytest (`pytest tests/run_q2b_collector_tests.py`)都会让整个会话以 INTERNALERROR 终止——**一个文件能干掉整次测试运行,且报错完全指向别处**。全仓无任何引用(脚本、workflow、文档均无) |
| **已处置(2026-10-12)**:归位到 `scripts/run_q2b_collector_tests.py`(shebang 与内容不变,仍可直接运行),全仓零引用故无影响。实测确认 `collect_ignore` **拦不住显式传路径**——pytest 对命令行显式给出的文件仍会导入,照旧 INTERNALERROR,所以真正生效的只有物理移出 |
| **JSON 产品在散文断言扫描面之外** | `scripts/real_product_assertions.py:66` 的 `_SCAN_SUFFIXES=(".md",".html",".txt")` 不含 `.json`——`--format json` 产品(含零条目空壳)从不进入 `run_assertions`;tech-ai-developer 曾仅凭 4 个 239–258B 零条目空 JSON(`entry_count: 0`)在差距矩阵判达标(#526 实测) | **已裁决(2026-10-17,#526):设计选择保持**——19 项断言为 prose 设计,把 `.json` 加进扫描面会引入假阳;no-data 防线的设计位置在 persist 边界(`autoinfo.output.is_no_data_product`,#385),空壳源头(CLI `output digest --persist` 无守卫)已由 #527 修复(#525);历史 4 个空壳已由验证侧重生成真产物。不加宽扫描面、不新增窄检查;若未来再现空壳落盘,先查 persist 闸是否被绕过,再议窄检查 |
| **MOBI 成功路径无自动覆盖** | `README` 把 EPUB/MOBI 标 ✅；唯一 mobi 测试 `tests/output/test_output_ebook.py:169` 是 `skipif(ebook-convert is not None)`——**只在 calibre 缺失时跑错误路径**。`ci.yml`/`nightly.yml` 均不装 calibre；`output-ebook.yaml` 注释自述 "mobi needs calibre, omitted" | 已登记(2026-10-22,#586)：README 状态改 🟡，本表为记录源；本地有 calibre 时可手工验证成功路径；是否把 calibre 装进 CI 另议(约 1GB) |
| **视频渲染缺浏览器(环境前提此前未登记)** | HyperFrames 走无头 Chrome 渲染,本机没有 Chrome(`PATH` 无,`~/.cache/puppeteer/` 只剩 `chrome-headless-shell` 残件),`report:video` 在三个验证域全部以 `RuntimeError: ... Chrome cannot launch` 失败;能力矩阵里归类为 `blocked-no-browser` | 已登记(2026-10-27,27×3 能力矩阵实测):**3 个 report:video 单元无法验证**,不是产物缺陷也不是代码缺陷,而是未写进依赖清单的环境前提。处置:安装完整 Chrome 后重跑该 3 单元;不得为让矩阵变绿而塞入 headless-shell 或静音失败——那会把"未验证"伪装成"已验证" |
| **KB 陈旧使 digest 拒产(`blocked-stale-sources`)** | `generate_digest` 的新鲜度闸门在所有候选条目都过期时抛 `StaleSourceError` 并拒绝出产物(有意的空壳防线,#525 同类);ai-commercial 仅有的 5 条 KB 条目建于 2026-08-15（采集于 08-14/08-15）,而 T11 收集到的 58 条新材料停在 gitignored `collections/`,处理层因缺 `AUTOINFO_LLM_API_KEY` 无法入库 | 已登记(2026-10-27,27×3 能力矩阵实测):**7 个 ai-commercial digest 单元因此未验证**,它是"拒产正确、数据未刷新"的诚实阻塞,不是生成缺陷。**注意它的成因链**:矩阵看到的"旧数据"本身是上游 blocked-key 的下游后果,补 key 后必须先 process 再重跑该 7 单元,否则矩阵仍会复现同一阻塞 |

## D. 系统变化触发的新表面(这是"新问题"的真实来源,不是"问题无穷")

| 变化 | 后果 | 对策 |
|---|---|---|
| 新功能 | 新代码面有覆盖缺口(#203 引入 $0.14M) | 新功能自带 QC 测试 + gate 断言 |
| 换模型 | 失败模式分布整体变化,规则需重推 | 换模型后重跑单次生产样本 |
| 修复引入回归 | 重生成可能带新问题(#207 的 404) | 修复必有测试 + 重生成后全 QC |

---

**判断"新问题"的口径**:先查登记表——
- 已在表中 = 已知类的再现,按对应检测层处理(通常可裁决或低成本修),**不算新发现**
- 不在表中 = 真新类,先登记再修(登记本身就把未知未知变成已知已知)
