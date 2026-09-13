# LOOP-LOG — AutoInfo validation 循环记录

> **活跃文档（2026-08-15 自 archive 复活）** — 每次迭代循环（打包/验证/修复）的**关键事件、根因、修复、验证结果**必须记录在此。
> 场景契约见 `docs/dev/validation-scenario-contract.md`；循环治理规范见 `docs/dev/validation-governance.md`。

> 机制说明（2026-08-12 首次落实，2026-08-15 重申）：
> - 每次迭代循环（打包/验证/修复）的**关键事件、根因、修复、验证结果**必须记录在此
> - 每次迭代**开始前**必须复查本文的「坑清单」——已知坑逐条核对，避免重踩
> - 新踩的坑当天追加到「坑清单」，格式：现象 → 根因 → 预防
> - 用户要求：迭代要形成文档，文档要在下次迭代前被复查，否则机制流于表面

---

## 2026-08-12 循环（第 1-9 次打包，11 个 issue 闭环）

### 打包迭代史（9 次）

| # | 结果 | 失败原因 | 分类 |
|---|------|----------|------|
| 1-4 | 弃用（exit-0 但 zip 未核验） | config.yaml tts 段丢失 → output-ebook 走 OpenAI TTS | 环境坑 |
| 5 | 170530.zip，4 scenarios failed | config 第 4 次丢失；premium 180s 超时；llm-gated 概率失败；data-lifecycle 游标 bug；gap=81 | 混合 |
| 6 | 195935.zip，gap 80 | filler 产物被 D1 gate 误拒（agent JSON-LD 用 markdown sections 标准）| 深层 bug |
| 7 | 211016.zip，gap 80 | #224 只改 quality.py，_build_product_output 丢 @type 标记，agent 判定未触发 | 修复不完整 |
| 8 | 运行中 | 验证 #225（@type 透传）后最终打包 | — |

### Issue 闭环清单（11 个）

| Issue | 问题 | 根因 | 修复 | 验证 |
|-------|------|------|------|------|
| #203 | enterprise-briefing 180s 超时 | 两层超时：asyncio wait_for + kind:cli subprocess 180s 独立默认，只修一层无效 | scenario timeout 覆盖 + cli/http 透传 | premium ALL PASSED（第 7 次重跑）|
| #204/#206 | gates 串行慢 / 并行崩溃 | — | 并行 + 去重 | — |
| #208 | 12 个 MCP 工具扁平错误 | 错误 envelope 不统一 | 标准 envelope | — |
| #210/#218 | TTS 默认 openai | **两层默认值**：TTSConfig dataclass + _dict_to_config YAML 解析硬编码，只改 dataclass 无效 | 双默认都改 local | load_config()=local；ebook ALL PASSED |
| #213 | batch 游标过期跳过新 items | progress 只有数量无内容指纹，同数量新 items 不重置 | start_index>=total 也重置 | data-lifecycle ALL PASSED |
| #215 | suggest_keywords LLM 空输出失败 | DeepSeek 概率空 content，无 fallback | deterministic 关键词提取 | llm-gated ALL PASSED |
| #217 | agent JSON-LD 被 D1 误拒（105 个） | **两层**：quality.py D1 判定 + validation_delivery 适配丢 @type | D1 agent-native 检查 + @type 透传 | D1/D2/D3 passed 实测 |
| #220 | presentation slides 空 | LLM 空 slides + 空 shell guard | KB-derived slides fallback | 6 cells 重跑全 OK |

### 坑清单（迭代前必查！）

1. **config.yaml 未提交修改在 checkout/并行操作时静默丢失**（WSL DrvFs，`.autoinfo/` gitignored）
   → 关键配置立即 commit 或 /tmp 备份；打包前置 `grep -q "tts:"` 自检
2. **`gh pr merge --delete-branch` 自动切回本地旧 main**——本地 main 落后远程（fetch 失败）时，后台任务读旧代码，修复"假阳性"
   → 每次 merge 后确认工作树分支与 sha；后台任务启动前 `git rev-parse HEAD` + grep 修复标记
3. **同一功能多层实现**：改一处默认/判定不够——修前 grep 所有相关层（dataclass/YAML 解析、asyncio/subprocess、gate/适配层）
4. **后台进程读启动时的工作树**：启动后再改代码不影响已启动进程——验证进程实际加载的版本
5. **WSL fetch/push GnuTLS 间歇失败** → 重试或 gh api 绕行；同步前确认 origin/main sha
6. **filler 生成的产物要过 D1 才算 produced**：产物存在 ≠ matrix 计入（gate 拒绝就不算）——验证走 manifest accepted
7. **agent JSON-LD 的 entry 字段按类型不同**：KnowledgeDigest=entries(source_url+source_platform)；KnowledgePresentation=slides(内容)+sources(来源)；KnowledgeTutorial=steps/exercises(内容)+source_entries(来源)——authenticity 必须按 @type 分支检查，不能一刀切
8. **生成端硬编码空字段**：generate_report agent 渲染曾 `source_platform: ""` 写死（KB 数据有值但产物空）——修生成端后**必须重新生成旧产物**（已生成的不变）
9. **_json_entries 对顶层含 _ENTRY_KEYS 交集的 dict 会整体当 entry**：KnowledgeTutorial 顶层有 title → 被误当 1 个 entry——按 @type 特判（source_entries）绕过
10. **html 模板必须输出 D1 三键章节**：report.html.j2 只有 Executive Summary，缺 Key Findings/Recommendations → D1 永远拒 report-html（模板 + 传参一起改，改完必须重新生成旧产物）
11. **适配层 product_type 粒度**：_build_product_output 曾把 product_type 全标 "PROCESSED" → quality.py D1 无法按产品分支——改为透传 _detect_product_type 结果（presentation/report/column/...），RAW 保持
12. **presentation 完整性语义 = slide 内容**：D1 三键不适用 deck——product_type==presentation 时 body 内容 ≥200 chars 即 pass（无需改模板视觉）
13. **persist 文件名决定 matrix evidence**：generate_report 曾把 column（report_type）产物固定存为 report-markdown-* → 文件名解析永远到不了 column:markdown cell（#229）——persist product 名必须与 spec product 对齐
14. **全量 validation 结果受 DeepSeek LLM 时段波动污染**（2026-08-14，PR #235 全量验证）：log 中 `Failed to parse LLM response as JSON` 63+ 次时，output-* 场景批量 failed——但隔离复跑证明与并发/代码无关（output-column 单独 passed 靠重试救回，output-digest-report 单独也 failed）→ 全量跑前先做 1-2 次短 LLM 探测（llm-gated 单场景 <60s passed 即稳定）；波动时段的重跑结果不可作为回归判定依据

### 复盘（为什么 9 次）

- 任务固有难度低：最终只有 2 个深层 bug（agent D1 误判、TTS 双默认）+ 若干流程坑
- 6-7 次失败是我的执行问题：① 环境坑反复踩（文档机制从未落实，坑没固化为检查项）；② 修复只修一层（未 grep 全层）；③ 验证假阳性（进程读旧代码，验证的是新代码）
- 教训：**修复前先扫全实现层 + 验证前确认进程读的代码版本 + 新坑当天进 LOOP-LOG**

## 2026-08-31 循环（跨域去重落地数据层：Dolly + URL 级）

### 关键事件
- **Dolly 跨域去重落地**：删 5 域 7 条讣告副本（b2b/financial/gaming/online-education/online-video），保留 4 语言学习域语言版本（教学价值）。commit 1a63d49
- **URL 级跨域去重**：ai-commercial × b2b 配置共享 producthunt/techcrunch/crunchbase 3 源 → 30 组同 URL 跨域重复。删 31 条（b2b 27/tech-ai-developer 3/ai-commercial 内部 1），保留高 rel。commit a78cce5
- 重生成：Dolly 4 域 × tutorial/presentation + b2b/tech-ai-developer 全 8 产品 = 24 文件，全部 Dolly=0 / clean

### 坑清单追加
15. **跨域重复有两层：事件级 + URL 级**。#109 只防事件级（跨语言讣告 proper-noun+死亡词+时间窗）；URL 级（同源多域采集）是配置层缺口——ai-commercial/b2b 共享 producthunt/techcrunch/crunchbase 源导致。根因是源配置重叠，正解是源去重归属（每源只归一域），删除数据只是交付物侧缓解。
16. **产品生成读 SQLite entries 表（KBStore().list_entries），不过滤 dedup_status**——清洗必须 SQLite + 01-Raw 双删，只删文件不够。`list_entries` 默认返回全部条目（含 duplicate），域内靠 `_converge_near_duplicates` 收敛，跨域不收敛。
17. **producthunt 产品页同 URL 不同 title 会误判**：Google Antigravity 的 IDE Extensions vs Remote Control 是产品页更新导致，判定跨域重复时要看 title 是否实质相同。
18. **manifest total_domains/total_products 是构建脚本硬编码**——域数变化后可能 stale（18 vs 实际 19）。打包后必须核验 manifest 统计字段与实际一致。
19. **report/column 厚域超时**（b2b.column exit=124 @400s）：重试 timeout 500 成功。reference 记录过 #106 cap 后仍可能超时，重试即过。
20. **gh token suspended 期间 git push/fetch 表现不同**：fetch 读正常（匿名/缓存），push 403（写需有效 token）。issue 提不了，先记录等 token 恢复。

### 2026-08-31 追加（column 命令纠正 + chaos guard 发现）
21. **`output report --type column` 不产出 column 模板**——只有 `--product column`（product_template 非 None）才走 column.md.j2（Big Idea/Deep Dive 结构）。`--type column` 是 T40 向后兼容：H1 保持 `{domain} — Report` + 标准 report 结构。**reference 里 `--type column` 的命令是错的**，正确命令：`output report --domain X --product column`。
22. **厚 KB 域 LLM 分组不稳定**：b2b report 52 themes/24 single-entry、column 47 themes/16 single-entry 触发 #106 chaos guard → 回退 deterministic 分组，分组标题用原始 source 名（HACKERNEWS/RSS/API）→ 产品正文出现非语义 `###` 标题。已提 #113。fallback 分组标题应改用领域主题词。

## 2026-09-13 循环（agent-oriented gap register 落地后的验证闭环审查）

### 关键事件
- **同步 backup/main `2e1052d`**（+1 commit / 295 文件 / +11833 / -2262）：62-gap agent-oriented register（7 waves / 41 tasks）、场景 138→159、诚实化 harness（error-audit truth gate、checkpoint/resume、per-step timeout）、agent-native surface（canonical envelope + outputSchema 全覆盖、CLI/REST/build/vendor parity）、新增 `scripts/ax_metrics.py` / `category_pyramid_coverage.py` / `build_release_check.py` / `docs/dev/testing-layers.md`。本地 `--ff-only` 至该 sha，三方校验一致（本地 = backup/main = gh api）。
- **CI 覆盖缺口（本轮前提）**：`AutoInfo_BackUp` 的 GitHub Actions 为 `enabled=false`（维护者有意保留——等主仓解禁；9 月末复核，若仍不解禁则把 backup 提升为 main 并开启）→ commit `2e1052d` 在 CI 侧**零覆盖**（check-runs=0；最近一次 run 为 2026-08-22，且当时含 `CI failure` / `Release failure`）。本轮因此由验证侧在本地**替代 CI** 复跑全部门。
- **本地替代复跑的门（全绿，逐条实跑）**：
  - `scripts/doc_inventory.py --check` → pass（149 tools / 35 categories / 5215 tests 全部 match，无 stray 文件）
  - `scripts/category_pyramid_coverage.py` → 159 场景扫描、14/20 cell 有场景、0 unclassified
  - `scripts/stage_user_coverage.py` → 126 cells / 126 classified、72 expectations / 72 classified、0 unclassified（`STATUS: OK`）
  - `scripts/error_message_audit.py` → 220 个错误调用点、raw-exception 站点 **0**、缺 fix hint **0**
  - `scripts/ax_metrics.py` → `GATE PASSED`（M-03~M-06 PASS；**M-01/M-02 UNMEASURED** 属脚本第 31-35 行文档化的有意行为：缺数据源时不判 pass 也不判 fail）
  - 测试套件：本地全量在 WSL 上跑不完（I/O 慢，>40 分钟），改为定向跑本轮 commit 改动的测试区（`tests/mcp` / `tests/validation` / `tests/cli` / `tests/output` / `tests/llm`）；全量跑的前 40%（2126 passed / 21 skipped）**零失败**。
- **提 issue #236**（documentation）：`2e1052d` 的 commit message 把改动集挂在 `.omo/plans/agent-oriented-gap-register.md` 上，但该文件既不在仓库也不在磁盘（`.omo/plans/` 另有 5 份已跟踪 plan）→ 41/41 tasks、F1–F7 APPROVE 在仓库内无法复核。修法二选一：补交该 plan，或按既有先例（`d69cc6b` 把 major-wave plan 提升到 `docs/dev/plans/`）。
- **提 issue #237**（bug + data）：跑测试会写脏**被跟踪**的 `collections/medical-research/pubmed/_runs.json`（根因 `tests/collectors/test_collection.py:543` 的 mock 失败 `"PubMed down!"` 经 ledger 落盘；该文件未被 gitignore）→ 每次跑测试留下脏树，且交付采集数据被夹具条目污染。

### 坑清单追加
23. **计划文件不在仓库 → 改动集不可复核**。commit message 引用的 plan（41/41 tasks、F1–F7 APPROVE）在仓库与磁盘都不存在；`.omo/plans/` 已是既定约定（5 份被跟踪），缺的是"提交"这一步。**预防**：任何引用计划的 commit，计划必须先在仓库内可寻址；或 message 指向仓库内真实文件。
24. **测试写进"真实环境"而不是隔离目录**。`tests/collectors/test_collection.py` 的 mock 采集失败会经 `src/autoinfo/collect.py` 的 ledger 写入落到**被跟踪**的 `collections/medical-research/pubmed/_runs.json`。**预防**：测试侧把 collections 根指向 `tmp_path`（或 monkeypatch ledger 路径）；跑完测试 `git status` 必须为空。
25. **「已知红预算」必须只有一份权威数字，且随 commit 更新**。`ci.yml` 注释称 12 documented M1-deferred envelope failures（引 TRIAGE.md #73-84），而 `tests/TRIAGE.md` 是 2026-08-05 的 83 failed + 1 error 基线；两者都过期且互相矛盾，本轮 commit 一个也没更新。**预防**：红色预算写在一处（TRIAGE.md 或独立基线文件），CI 注释只引用不复述；数据变更的 PR 必须同步该数字。
26. **"UNMEASURED" 不等于 "未通过"，验证报告必须如实区分**。`ax_metrics` 在缺数据源时报告 UNMEASURED 且不影响 gate 结论（有意设计，脚本内已文档化）。验证方若把 UNMEASURED 概括成"门在真空通过"就是误报（本轮我第一版汇报即如此措辞，查源码后更正）。**预防**：报告里把「通过 / 未测量 / 失败」三态分开写，不合并成一句结论。
27. **本地 editable 安装陈旧会伪装成"仓库缺陷"**。`build_release_check.py` 的 "installed version == source version" 一条在本机失败（installed 1.8.1 vs source 1.11.0），根因是本机 `.venv` 的 editable metadata 过期，不是仓库问题。**预防**：跑发布面门前先确认 `pip install -e .` 是最新的，否则该门结论无效。

## 复盘记录（fix-retro，2026-09-07 起）

> 每轮修复完成后按 `fix-retro` skill 输出复盘块（5 问）追加到此段。目标：不只记坑，沉淀模式——根因分类统计 → 重复模式识别 → 预防措施 → 技能沉淀。复盘块的根因分类基于失败定性协议（validation-governance.md），不凭印象。

## 复盘（fix-retro @ 2026-09-13）

**本轮修了什么**（本轮为**审查轮**：新增 2 个 issue，仓库侧修复待做；门全部复跑）:
- 新增 issue **#236**: 计划文件 `.omo/plans/agent-oriented-gap-register.md` 未入库 → 41/41 tasks 与 F1–F7 APPROVE 不可复核（文档/可追溯）
- 新增 issue **#237**: 测试写脏被跟踪的 `collections/medical-research/pubmed/_runs.json`（数据污染 + 脏树）
- 已确认**无红门**：`doc_inventory --check` / `category_pyramid_coverage` / `stage_user_coverage` / `error_message_audit` / `ax_metrics` 五门全绿；测试全量前 40% 零失败（本地 WSL 跑不完全量，改定向跑）

**根因分类统计**（基于失败定性，非印象）:
| 类型 | 数量 | 例子 |
|------|------|------|
| 文档/可追溯 | 2 | #236 计划未入库；#25 已知红预算两处数字矛盾且过期 |
| 环境/配置 | 2 | #237 测试写真实 tracked ledger；#27 本地 editable metadata 陈旧（非仓库缺陷） |
| 过程/治理 | 1 | CI 关闭导致的零覆盖（维护者有意为之，9 月末复核）+ 本轮未按规范记 LOOP-LOG |
| 报告口径（验证方自身） | 1 | #26 把 UNMEASURED 误述为"门在真空通过"，查源码后更正 |

**模式识别**（重复出现的根因 → 系统性问题）:
- **模式 1：明确写入规范的东西没有被执行**（出现 2 次）。LOOP-LOG 头部自己写着"每次迭代循环的关键事件/根因/修复/验证结果**必须**记录在此"，本轮 295 文件的改动集却没有记录；`.omo/plans/` 已是既定约定、plan 提升到 `docs/dev/plans/` 也有先例，但被引用的计划没进仓库。
  **系统性解读**：规范文本与执行之间没有**机械检查**。姊妹仓库（AutoMedia / omni suite）的同类问题都是靠"变成可执行闸"解决的（如 doc_inventory 的 claim sites、pre-commit 入口检查）。本仓库的 doc_inventory 已经很强，但它不检查"本轮是否记了 LOOP-LOG"，也不检查"commit 引用的路径是否存在"——后者是最容易加、也最通用的一条。
- **模式 2：验证结论的"数据来源"与"数据可信度"没有分开表达**（出现 2 次：#25 的红色预算、#26 的三态混淆）。`ci.yml` 复述了一份别处的、过期的失败清单；验证报告把"未测量"并进"通过"。
  **系统性解读**：数字一旦被复制到第二个地方就会漂移；门一旦允许"缺数据即跳过"，报告就必须显式暴露"跳过了什么"。这是个**表达纪律**问题，靠规范文本约束，靠报告模板固化。

**预防措施**（哪些可以 gate 预防而非事后修）:
- **commit message 里的路径必须存在**：加一个轻量 pre-commit / CI 检查（提取 message 中的 `.omo/...` / `docs/...` 路径 → 断言 `git ls-files` 命中）。本轮的 #236 是纯粹可机械拦截的缺陷。
- **测试不得写脏被跟踪文件**：把"跑完测试后 `git status --porcelain` 为空"纳入验证基准（本轮已人工执行，可固化为脚本）；测试侧一律隔离 collections 根（#237）。
- **红色预算单一权威源**：把失败清单集中到一处（`tests/TRIAGE.md` 或独立基线文件），`ci.yml` 只引用不复述，并在改动测试的 PR 里要求同步更新该数字。
- **本地复跑发布面门之前先刷新 editable 安装**（否则 #27 这类假失败会反复出现）。
- **CI 覆盖缺口显式登记**：Actions 关闭期间，每个改动集都必须在 LOOP-LOG 里留下"本轮门由本地复跑"的记录与本机环境信息（Python/pytest 版本），否则日后无法判断结论的有效性。

**沉淀**（新的 skill/checklist/坑清单条目）:
- 坑清单 23–27（见上）。
- 通用工作法（跨项目）：**"验证报告三态分离"**——通过 / 未测量 / 失败必须分开写，禁止合并成一句结论；以及**"门的作用域必须与实际数据来源匹配"**（缺数据时门要么 fail-loud，要么在报告里点名跳过了哪些检查）。

### 复盘模板（首轮复盘在下一轮修复后追加）

```markdown
## 复盘（fix-retro @ YYYY-MM-DD）
**本轮修了什么**:
- issue #NNN: 一句话

**根因分类统计**:
| 类型 | 数量 | 例子 |
|------|------|------|
| 类型错误 | N | ... |
| 边界/空值 | N | ... |
| 环境/配置 | N | ... |
| 依赖/版本 | N | ... |
| 其他 | N | ... |

**模式识别**（重复出现的根因 → 系统性问题）:
- 模式: ...（出现 ≥2 次）
- 系统性解读: ...

**预防措施**（哪些可以 gate 预防而非事后修）:
- ...

**沉淀**（新的 skill/checklist/坑清单条目）:
- ...
```
