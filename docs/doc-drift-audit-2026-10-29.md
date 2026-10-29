# AutoInfo 文档漂移审计报告

**日期**：2026-10-29（HEAD = 45eeed1d，v1.21.4）
**方法**：静态核对（计数用 grep/脚本实测，非目测）+ git 最后触达日期 + 逐条对照代码。凡本文断言"漂移"的条目，均给出 doc 原文位置与代码证据位置；无法确证的未列入。
**范围**：README.md、AGENTS.md、docs/dev/specs/ 全部、glossary、cross-dimensional-catalog、required-api-keys、doc-inventory 及防漂移工具本身。未核对 docs/archive/（按项目约定不维护）。
**配套关系**：`docs/project-analysis-2026-10-29.md`（同日）分析项目问题；本报告只回答一个问题——**哪些现有文档与当前代码不一致、需要更新**。

> **修复状态（2026-10-29 同日更新）**：P1-1 至 P1-5、P2-1、P3-1、P3-3 及第五节 doc_inventory 平台盲区均已按"修法"落地；P2-2 已完成 process 阶段三项语义补写；P3-2 按原建议留待随相应域变更顺带更新。本文保留为**审计时点快照**，其"漂移"描述描述的是修复前的状态。

---

## 一、总体结论

项目的计数防漂移机制是真实有效的：**README/AGENTS 的八个守门事实全部与代码实测一致**（149 MCP 工具、35 类别、31 CLI 组、13 投递渠道、182 场景、21 域、16 LLM 必需工具、测试数，逐项实测见附录）。漂移不在"计数"，而在**散文性描述**——防漂移守门（`doc_inventory --check`）比的是这八个数字（外加 `SKILL_FACTS` 7 项镜像比对与 `LIVING_DOCS` 9 份文档的正则扫描），比不了语义。本次共确认 **9 项需要更新的漂移**，按优先级列下。

其中最重要的一条：**AGENTS.md 对 judgment-model 行为的描述与代码相反**（详见 P1-1）。AGENTS.md 是 agent 的第一操作手册，这条会直接误导 agent 对系统的理解，建议最先修。

---

## 二、P1 — 实质性错误（会误导读者/agent，应尽快修）

### P1-1. AGENTS.md：judgment-model 描述与代码相反 ⭐ 最重要

- **AGENTS.md 原文**（"Per-task model routing (2026-08-13)"段）：judgment 调用（G4 factual、G5 translation、llm_judge）"resolve to the release-pinned `JUDGMENT_MODEL = "deepseek-v4-flash"` **constant** (config.py, beside `LLMConfig`) — a release-level decision, never runtime task-config drift"。
- **代码实际行为**：config.py:127-151 明确注释 "judgment-model resolution is now **config-first** ... NOT as a code constant"（issue #195，2026-09-03）。现在代码里只有 `JUDGMENT_TASKS` frozenset（config.py:151），解析链为 `llm.judgment_model`（default_config.yaml 已带出厂默认值）→ `llm.model` → 抛 `JudgmentModelNotConfiguredError`（quality.py:78-105、1329、1641 实装）。**代码中已不存在 `JUDGMENT_MODEL` 常量。**
- **矛盾方裁定**：`docs/dev/specs/pipeline.md:389` 描述的是 config-first，与代码一致；**AGENTS.md 是过时的一方**。
- **讽刺点**：AGENTS.md 最后一次触达是 2026-10-26（e22d1edc），即代码 09-03 改掉之后它被改过至少一轮、这段却始终没跟上。
- **修法**：改写该段为 config-first 三级链 + `JudgmentModelNotConfiguredError` 语义；同时删去"release-pinned constant"的定性（这是 #127 ghost-model 事故后有意废弃的机制）。

### P1-2. required-api-keys.md：缺 Azure TTS 的两个环境变量

- **事实**：v1.21.0（PR #647，2026-10-28）新增 Azure Speech TTS 引擎，凭据从 `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` 读取（config.py:619-628、output/audio.py:45-51）。
- **漂移**：`docs/dev/required-api-keys.md`（09-29）全文约 40 个变量，但 Core 小节（41-42 行）只登记了 `AUTOINFO_LLM_API_KEY` 和 `OPENAI_API_KEY`，且**两个 AZURE_SPEECH_* 变量在全文任何小节均未收录**。该文档的自我定位就是"Full catalog of API keys and environment variables"（AGENTS.md References 语），是 key 目录的单一事实源。
- **修法**：按现有表格式补两行（变量、用途=Azure 引擎 `format=audio` 渲染、可选性、代码位置 output/audio.py + config.py）。

### P1-3. README.md：Audio output 状态行与技术栈表未反映 Azure 引擎

- **README:44**（Status 表）："`Audio output` | TTS-rendered digest/report as MP3 (**OpenAI TTS**)"；**README:288**（技术栈表）："edge-tts (TTS audio, optional)"。
- **代码实际**：音频引擎现为四种——`local`（edge-tts，默认）、`openai`、`whisper`、`azure`（audio.py:123-126），由 `tts.engine` 配置键选择（config.py:610）。
- **背景**：PR #647 对 README 只改了测试计数一行（6612→6630，PR 信息自认"drift guard 现在才过"），Status 行没跟上。防漂移守门只锁计数，锁不了这行散文——这正是守门机制的已知盲区在本项目自己身上的应验。
- **修法**：README:44 补引擎清单与 `tts.engine` 配置键；README:288 在可选依赖处补 azure 引擎一句。

### P1-4. glossary.md：质量门禁词条停在 G0-G5，缺 G7

- **glossary.md:21**："G0-G5 | Quality gates: G0 Schema (hard), G1..., G4 Factual (hard), G5 Translation"。
- **实际**：G7（entity-fact consistency，确定性检查、honest hedge 不标记）早已是正式门禁——AGENTS.md 门禁表和 `specs/quality-gates.md`（10-24 更新）均收录。
- glossary 最后触达 2026-08-13，是 specs 之外最老的一份活文档。作为"Ubiquitous Language 权威定义"，缺 G7 意味着按 glossary 说话的 agent 会漏掉一个正式门禁。
- **修法**：补 G7 词条（一行即可）；顺带核对 D1-D3 词条现状（这部分与 AGENTS.md 一致，无需动）。

### P1-5. specs/delivery.md：产品×格式矩阵落后于 README 与代码

- **delivery.md:15-16**（产品表）：Digest 格式为 "Markdown, HTML, Plain Text, Audio"；Report 格式为 "Markdown, JSON, PDF, HTML, Audio"。
- **README:42 / 代码**：Digest 另支持 **JSON/Agent/EPUB/Audiobook**；Report 另支持 **Agent/Video/EPUB/Audiobook**。ebook.py（EPUB/MOBI/audiobook）与 video.py 管道均已落地。`output/__init__.py:2871` 的 Digest `valid_formats` 实为 `{markdown, html, json, agent, audio, epub, audiobook}`，`:3602` 的 Report 再额外含 `video`。
- **文档内自相矛盾**：同一文件的 Magazine Digest 行（第 19 行）已写 "Markdown, HTML, JSON, Agent"，与第 15 行基础 Digest 行冲突——说明这行不只是落后，而是自相矛盾。
- **反向漂移（文档多写）**：delivery.md 原列的 Digest "Plain Text" 与 Report "PDF" 在代码里都不存在——`generate_digest` 的 `valid_formats` 无 `plain`/`text`，`generate_report` 的格式白名单无 `pdf`（`tests/output/test_report.py:244` 断言 `format="pdf"` 抛 `ValueError`）。README:42 也从未把 PDF 列在 report 下。即这两行同时存在"漏新增"和"多在册"两种错误。
- delivery.md 最后触达 2026-08-19，落后两个多月；它还是 doc-manager-skill 依赖映射里"产品/格式变更必更新"的文档。
- **修法**：更新两行格式清单；建议同时在 delivery.md 补一小节 TTS 引擎选择（现在全文无 engine 概念，只有 "TTS MP3" 字样）。

---

## 三、P2 — 新能力未入文档（功能已在代码/CI，文档缺位）

### P2-1. `--since-days` / `--newest-first`（#655，合并于本审计当日）

- 代码已实装：`cli/process.py:61-69`、`process.py`、`scripts/nightly_process.py`。
- **全部文档零覆盖**：grep `since-days|newest-first` 在 README、AGENTS、docs/** 仅命中未跟踪的分析报告与 archive 目录。按 doc-manager-skill 自己的依赖映射（"CLI flag change → README / AGENTS / cli-mcp-rest-parity.md"），本次变更至少漏了这三处中的两处。
- **修法**：`docs/dev/cli-mcp-rest-parity.md` 的 process 节补两个 flag；README 的 CLI 快查节（~322 行）可视需要补一句。

### P2-2. specs/pipeline.md：process 阶段落后三个大版本改动

pipeline.md 的 LLM 段（383-389 行：信号量、退避、per-task 路由）是新的、与代码一致，**不需要动**。但 process 阶段自 09-03 以来发生了三件大事，全部无记载：

| 改动 | 版本 | pipeline.md 现状 |
|---|---|---|
| nightly 硬预算 + fair-share 批调度（#635） | 1.18.0 | 无 budget/fair-share 描述 |
| 处理游标改为按 item id 单调推进（#637） | 1.21.3 | §collect 有游标概念（125 行），process 游标语义未更新 |
| `--since-days`/`--newest-first`（#655） | 1.21.4 | 无（即 P2-1） |

连续两个 fix 都在修"预算内的运行够不着新条目"，说明 process 阶段语义已实质变化，pipeline.md 的对应章节值得重写一遍。

---

## 四、P3 — 结构性滞后（不误导日常操作，但"单一事实源"地位已动摇）

### P3-1. cross-dimensional-catalog.md（09-13）

自定位为 126 格产品矩阵、42 个 gap 的**单一事实源**。但 10 月的 #638/#640/#642 完成了 81 格证据包、逐行源诊断、KB 索引对齐，且 `pkg-AutoInfo/`（10-26）登记了 **832 格中 322 格空缺、78 组零原始数据**——目录中的 🟢/🟡/🔴 分布已不可信，两份"gap 真相"开始并存。它在 AGENTS.md 里被标注为 keystone，应随 T2 产能补齐工作同轮刷新（project-analysis 报告建议 #5 与此同源）。

### P3-2. operations.md（08-23）、market-positioning.md（08-13）、ops-runbook.md（08-13）

均两个多月未触达。未发现硬错误，但按各文档主题，Azure TTS 引擎（operations 的 capability 表只到 "audio_output: TTS-rendered as MP3"）与近两个月的运行语义（预算调度）都尚未进入。优先级低于 P1/P2，建议随下一次相应域的变更顺带更新。

### P3-3. development-brief v2/v3/v4 + AutoInfo开发简报.md 仍标 active

doc-inventory.md:77-80 中四个 brief 全部 `active`。9-17 评估已指出"三版并存未归档"，至今未动。属已知旧账，本报告仅确认其仍成立：建议归档 v2/v3、保留 v4 为活文档并在 inventory 中把 v2/v3 置 `archived`。

---

## 五、工具性发现：防漂移守门自身在本机不可运行

`python scripts/doc_inventory.py --check` 在本机（Windows）直接崩溃：

```
File "scripts\doc_inventory.py", line 358, in _venv_interpreter
    return cand if cand.is_file() else None
OSError: [WinError 1920] 系统无法访问此文件。: 'D:\\贯维\\AutoInfo\\.venv\\bin\\python'
```

根因：`_venv_interpreter()` 只探测 POSIX 布局的 `.venv/bin/python`，Windows 应为 `.venv/Scripts/python.exe`；对不可访问路径的 `stat` 在 Windows 上抛 OSError 而非返回 False（脚本未捕获）。**守门机制存在平台盲区**——CI（Linux）上正常，Windows 开发机上"跑了才知道"的第一道文档防线直接不可用。建议纳入 backlog（小改动：候选路径列表加 `Scripts/python.exe` + try/except OSError）。

---

## 六、核实无误的部分（避免失衡画像，也是对守门机制的验证）

以下计数经本次**实测**（非引用文档）与文档一致：

| 事实 | 文档声明 | 实测方法 | 结果 |
|---|---|---|---|
| MCP 工具 149 | README/AGENTS | `_TOOL_DISPATCH` 字典键计数（server.py:497） | 149 ✓ |
| CLI 命令组 31 | README/AGENTS | `app.add_typer` 计数（cli/__init__.py） | 31 ✓ |
| LLM prompt 16 | AGENTS.md | `data/prompts/` 文件数 | 16 ✓ |
| ErrorCode 29 值 | AGENTS.md | errors.py 枚举成员计数 | 29 ✓ |
| ADR 11 份 | — | docs/adr/ 下 `0*.md` 计数（13 个 .md 中含 README.md + TEMPLATE.md，非 ADR） | 11 ✓ |
| specs 12 文件 | AGENTS.md | docs/dev/specs/ 计数（11 md + 1 yaml） | 12 ✓ |
| demo 域 21 | README/AGENTS | data/domains/ 目录数（扣除 __init__） | 21 ✓ |
| 验证场景 182（86+96） | README | scenarios/**/*.yaml 递归计数 | 182 ✓ |
| 采集器 ~30 handler | README/AGENTS | collectors/ 31 个 handler 文件 + registry 别名注册（email/email_imap、huggingface/kaggle 同 handler），与"30"口径一致 | ✓（不判漂移） |
| "8 product templates" | README:42 | templates/ 下 *.md.j2 恰 8 个（另有 3 个 html.j2 渲染模板） | ✓（表述可更精确，见下） |

**一处表述澄清**（不算错误）：README/AGENTS 的"8 output product templates"实指 8 个 `*.md.j2`；`data/templates/` 实有 **11 个 .j2**（多出的 3 个是 digest/report/presentation 的 html.j2）。建议文档补一句口径说明，防止下一个人像我一样误报漂移。

---

## 七、修复优先级汇总

| # | 文档 | 问题 | 工作量 |
|---|---|---|---|
| 1 | AGENTS.md | judgment-model 描述与代码相反（常量→config-first） | 小（改一段） |
| 2 | required-api-keys.md | 补 AZURE_SPEECH_KEY / AZURE_SPEECH_REGION | 小（两行） |
| 3 | README.md:44/288 | Audio 行补 azure/whisper/local 引擎与 tts.engine | 小 |
| 4 | glossary.md | 补 G7 词条 | 小（一行） |
| 5 | specs/delivery.md | 产品格式表补 EPUB/Audiobook/Video/Agent；补 TTS 引擎节 | 中 |
| 6 | cli-mcp-rest-parity.md + README | 补 --since-days / --newest-first | 小 |
| 7 | specs/pipeline.md | process 阶段补预算/公平调度/单调游标 | 中 |
| 8 | cross-dimensional-catalog.md | 产能状态全面刷新（随 T2 工作同轮） | 大 |
| 9 | development-brief v2/v3 | 归档置 archived | 小 |
| — | scripts/doc_inventory.py | Windows venv 探测崩溃（守门工具自身） | 小 |

#1-#6 都是"一个小节/几行"级别，可合为一个 docs PR；#7-#8 建议分别随相应功能工作顺带完成。全部修完后在能跑 CI 的环境（或先修 doc_inventory 的 Windows 路径问题）重跑 `doc_inventory --check` 确认 exit 0。

> **合入前必做**：本报告与 `docs/project-analysis-2026-10-29.md` 新增到 `docs/` 后，`docs/dev/doc-inventory.md` 即变为 stale，`doc_inventory --check` 会以 exit 1 报 `docs/dev/doc-inventory.md is stale`（本次实测确认）。合入前需先跑一次 `python3 scripts/doc_inventory.py` 重新生成 inventory 表。

---

## 附：证据索引

| 断言 | 证据 |
|---|---|
| judgment 为 config-first | config.py:127-151（注释与 `JUDGMENT_TASKS`）；quality.py:78-105、1329、1641；`JUDGMENT_MODEL` 常量 grep 0 命中 |
| AGENTS.md 原文 | AGENTS.md "Per-task model routing (2026-08-13)" 段 |
| Azure 凭据变量 | config.py:619-628（`AZURE_SPEECH_REGION`/`AZURE_SPEECH_KEY`）；output/audio.py:45-51 |
| required-api-keys 缺失 | docs/dev/required-api-keys.md:41-42（Core 小节仅 AUTOINFO_LLM_API_KEY、OPENAI_API_KEY；`AZURE_SPEECH` 全文 0 命中） |
| PR #647 只改 README 计数 | `git show e29b1d3b -- README.md`（6612→6630 一行） |
| 引擎四种 | output/audio.py:123-126 docstring（local/openai/whisper/azure） |
| glossary 停在 G0-G5 | docs/glossary.md:21；G7 grep 0 命中 |
| delivery.md 格式落后 | specs/delivery.md:15-16 vs README.md:42 |
| since-days 零文档覆盖 | grep `since-days|newest-first` 于 docs/** + README + AGENTS：仅未跟踪报告与 archive 命中 |
| pipeline.md LLM 段是新的 | specs/pipeline.md:383-389 与 AGENTS.md LLM 表逐条一致 |
| doc_inventory 崩溃 | 本文第五节 traceback（`_venv_interpreter`，scripts/doc_inventory.py:358） |
| 149/35/31/13/182/21/16/6665 | 第六节表中逐项实测方法（FACTS 8 项守门事实） |
