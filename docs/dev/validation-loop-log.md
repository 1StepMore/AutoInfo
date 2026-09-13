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

## 复盘记录（fix-retro，2026-09-07 起）

> 每轮修复完成后按 `fix-retro` skill 输出复盘块（5 问）追加到此段。目标：不只记坑，沉淀模式——根因分类统计 → 重复模式识别 → 预防措施 → 技能沉淀。复盘块的根因分类基于失败定性协议（validation-governance.md），不凭印象。

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

## 2026-09-14 循环（6 issue 修复 + PR #238 审查）

### 关键事件
- 审查 2026-09-13 轮（记录在 PR #238 `docs/loop-log-retro-20260913` @ `2c5a100`）提出的 6 个 issue，逐条复现并修复：
  - **#236** 计划入库：`.omo/plans/agent-oriented-gap-register.md` 提升为 `docs/dev/plans/agent-oriented-gap-register.md`（`<!-- doc-type: plan -->` + Outcome）。
  - **#237** dry-run 不写 ledger：`collect.py` 的 skipped / SourceFailure / 通用异常三分支的 `_log_run` 加 `not dry_run` 闸；测试侧用 `monkeypatch.chdir(tmp_path)` 隔离。
  - **#239** 单一权威红预算：`tests/TRIAGE.md` 新增权威段（环境三元组 + 2594/17/2553/24/0），`ci.yml` 改为只引用不复述，新增 `test_known_red_budget_single_source.py` guard。
  - **#240** 文档再生 + 闸：`render_enduser_coverage_view` 以 `\n\n` 结尾，而 pre-commit 的 `end-of-file-fixer` 每次提交把尾随空行规范化掉，于是产物与生成器永久不一致（真根因，不是手改）；生成器改为只输出单个尾随换行，`make doc-check` + CI 步骤跑 `--check-enduser-doc`。
  - **#241** 时间炸弹：`test_tutorial_no_placeholder.py` 的绝对 `collected_at` 改为相对时间戳。
  - **#242** CLI 错误 envelope：`cli/_EnvelopeGroup` 顶层 seam，usage error / 未知命令 / 未捕获异常在全局 `--json` 下都产出规范 envelope。
- **PR #238 审查**：docs-only（2 commits / 仅 `validation-loop-log.md` / +71），`git merge-tree` 干净（可 fast-forward）。未合并（远端写操作待人工批准）。
- **两处对 2026-09-13 轮结论的更正**（本轮复现所得）：
  1. **#242(b) 跨文件泄漏是假阳性**：合规环境（Python 3.11.15 + pytest 8.4.2）下 `test_fault_injection.py` + `test_cli_json_parity.py` 成对跑 **9/9 通过**；上一轮的 3/3 复现来自非合规环境（pytest 9.1.1 + 无插件），即坑 #28/#29 所述。
  2. **#241 的"gaming TTL 短"不成立**：`DomainConfig.domain_defaults` 未列 gaming，其 TTL 与 general-news 一样是 90；真正触发是 `calculate_freshness_score` 的 `freshness < 0.5`，等价于 `age_days > ttl_days/2`（45 天）。

### 坑清单追加（迭代前必查）
30. **CLI `--json` 错误路径要覆盖"回调之前"的解析错误**。`click.Group.invoke` 的顺序是 `resolve_command`（未知命令/组级坏 flag 在此报错）→ root callback（`--json` 才置位 ContextVar）→ 子命令 `make_context`（子命令 usage error）。所以未知命令/组级坏 flag 发生时 ContextVar 还没置位，只读 ContextVar 的顶层 handler 会漏。**预防**：从原始 argv 的**前导 option** 探测 `--json`（遇第一个非 `-` token 即停，避免把 `domain list --json` 误判为全局），并强制 `standalone_mode=False` 让 Click 不再自行打印/退出，再在顶层统一发 envelope。注意 Typer 0.27 vendor 了 Click，`typer._click.exceptions.BadParameter` **不是** `click.exceptions.UsageError`，要用 `exit_code` 等结构特征判断。
31. **"测试写脏被跟踪产物"要两层同修**：产品侧契约（`dry_run` = 无存储副作用）在错误分支上违约，测试侧又没隔离 cwd。只修测试 → 产品继续违约；只修产品 → 其他非 dry_run 测试继续写真实树。**预防**：两层一起修，并把"跑完 `git status --porcelain` 为空"作为回归门槛。
32. **"已知红预算"只能有一份权威数字**：`ci.yml` 复述 `TRIAGE.md` 的数字必然漂移（本轮发现 ci=12 vs TRIAGE=83+1）。**预防**：单一权威段（TRIAGE.md），其余文档只引用不复述，并加 guard 测试机械拦截"数字复述"。
33. **验证结论必须区分"环境假红"与"真实缺陷"**。本地 editable 元数据陈旧、pytest 违反 pin、套件不 hermetic，三者都会造出假红。**预防**：报告任何"红"之前，先过三条伪红判据（环境合规？子集/全集一致？产物相对生成器新鲜？），并登记解释器与关键依赖版本。
34. **生成器输出与 pre-commit 规范化 hook 冲突 → 永久漂移**。`coverage_matrix.py` 的 `\n\n` 结尾每被 `end-of-file-fixer` 规范成 `\n`，于是"再生成"永远和产物不一致（#240 的真根因，不是手改）。**预防**：生成器只输出单个尾随换行；遇到"生成物 vs 手改"类漂移，先检查 pre-commit 规范化 hook（trailing-whitespace / end-of-file-fixer）是否是真正的手。

### 本轮验证（定向，不跑全量）
- `make doc-check` → exit 0（doc_inventory --check + `--check-enduser-doc` 双绿）
- `pytest tests/collectors/test_collection.py` → 32 passed；`git status --porcelain -- collections knowledge` 为空
- `pytest tests/output/test_tutorial_no_placeholder.py` → 7 passed
- `pytest tests/cli/test_cli_json_parity.py` → 8 passed；`python3 -m autoinfo.cli --json cost dashboard --days abc` → 合法 envelope + exit 2
- `pytest tests/validation/test_known_red_budget_single_source.py` → 2 passed
- 场景库 161（86 functional + 75 regression），两个新回归场景可解析

### 复盘（fix-retro @ 2026-09-14）
**本轮修了什么**（审查 + 修复轮：2026-09-13 轮新增的 6 个 issue 全部闭环）:
- #236 计划入库；#237 dry-run 闸 + 测试隔离；#239 单一权威红预算 + guard；#240 文档再生 + 双闸；#241 时间炸弹；#242 CLI 全局 `--json` 错误 envelope。

**根因分类统计**:
| 类型 | 数量 | 例子 |
|------|------|------|
| 边界/空值 | 2 | #237 dry_run 错误分支漏闸；#240 生成器与产物差一个尾随空行 |
| 测试非确定性 | 2 | #241 绝对时间戳 + 新鲜度阈值；#242(b) 跨文件泄漏（实为环境假红） |
| 文档/可追溯 | 2 | #236 计划未入库；#239 红预算两处矛盾且过期 |
| 环境/配置 | 1 | 本地 editable/pytest 版本非合规导致的上一轮假红与误判 |
| 产品契约缺口 | 1 | #242 全局 `--json` 未覆盖回调前的解析错误 |

**模式识别**:
- **模式 1：明确写入契约的东西没有被机械检查**（≥2 次）：`dry_run` 的"无存储副作用"没有覆盖错误分支；`--json` 的"总是 envelope"没有覆盖回调前的解析错误；`TRIAGE.md` 的单一权威被 `ci.yml` 复述。**系统性解读**：契约需要变成可执行的闸（测试/guard），而非只是注释。
- **模式 2：验证结论的有效性依赖环境与产物对齐**（继承上一轮）：本轮再次踩到（上一轮 4 条假缺陷 + 本轮更正 2 条结论）。**系统性解读**：伪红三条判据应固化为报告前置步骤。

**预防措施**:
- 新增 guard：`test_known_red_budget_single_source.py`（数字单一权威）；`make doc-check`（coverage 文档不得漂移）；两个回归场景（#237 dry-run 无 ledger、#242 CLI 错误 envelope）。
- 报告模板固定"三态分离"（通过 / 未测量 / 失败）与伪红三条判据。

**沉淀**:
- 坑 30-33（见上）。
- 可复用 checklist：① 环境合规？② 子集/全集一致？③ 产物相对生成器新鲜？三条全过再把"红"当真。
