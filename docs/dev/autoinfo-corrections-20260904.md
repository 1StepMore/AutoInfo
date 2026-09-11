# AutoInfo 报告修正清单（concierge wave · todo 1 机读工作文件）

> **生成**: 2026-09-04 · **状态**: pending-application（todo 2 按本清单执行 in-place 修正）
> **修正对象**: `docs/dev/autoinfo-business-validation-20260902.md`（293 行）+ `docs/dev/autoinfo-dev-roadmap-20260902.md`（135 行）
> **文件性质**: 中立机读记录 — 每项含 文件:行号 / 原文（逐字片段，可 grep 定位）/ 新文（含 `[已修正 2026-09-04]` 标记）/ 证据来源 / 旧值→新值。
> **行号基准**: 2026-09-04 当前磁盘状态（两份报告文件未被任何任务修改；行号已逐条对照当前文件核实）。
> **特殊标记**: `verified-correct (keep)` = 核实为正确、保持不动的注记项（验证断言跳过其"原文≠当前行"检查）。
> **不裁决项**: demo zip 的处置（重建/删除/替换）留待 todo 2 — 本清单仅记录"文件不存在"这一发现（C-03/C-24/C-33）。
> **证据缩写**: `draft` = `.omo/drafts/autoinfo-report-validation-concierge-wave.md`（findings 行 30-56 / 市场声明 V1-V12 行 60-74 / 定价 P1-P10 行 76-88）。

## 索引

| ID | 位置 | 类型 | 摘要（旧→新） |
|:---|:-----|:-----|:--------------|
| C-01 | business-validation:4 | correction | R5"通过独立审查"→"自检通过、审查报告未存档" |
| C-02 | business-validation:22 | correction | 663 提交→665；150→151 |
| C-03 | business-validation:27 | correction | demo zip 存在→文件与 deliverables/ 均不存在[未验证] |
| C-04 | business-validation:28 | correction | R5 独立全量审查→自检行、无审查报告存档 |
| C-05 | business-validation:53 | correction | TLDR/Pragmatic Engineer 定价模式混用→拆分标注 |
| C-06 | business-validation:63 | correction | Reddit 逐字引语→转述标注 |
| C-07 | business-validation:64 | correction | Reddit 逐字引语→转述标注 |
| C-08 | business-validation:82 | correction | AlphaSense per-seat/合同总额混用→加溯源注释 |
| C-09 | business-validation:84 | correction | Readless Free→无永久免费层（7 天试用） |
| C-10 | business-validation:85 | correction | Competely $39-$59→$39/$59/$99（补 $99 档） |
| C-11 | business-validation:115 | correction | BlogWatcher 误标 anthropics/skills→KiwiClaw/OpenClaw/Hermes 生态 |
| C-12 | business-validation:125 | correction | changedetection.io "$8.99 DIY"→自托管免费/SaaS $8.99 |
| C-13 | business-validation:127 | correction | R1-R13 硬扫→L0 门控 F1-F4/C1-C6/X1 |
| C-14 | business-validation:133 | correction | "$8.99/月 DIY 化"→自托管免费/SaaS $8.99 |
| C-15 | business-validation:135 | correction | R1-R13→L0 门控；D1-D5→D1-D3 |
| C-16 | business-validation:145 | correction | GVR CI 市场 $823.4M→[来源未验证] |
| C-17 | business-validation:146 | correction | GVR AI Agent $10.9B(2026)→2025 基值 $7.63B（部分确证） |
| C-18 | business-validation:147 | correction | DNR 16% 全球→18%（20 国篮子，DNR 2025） |
| C-19 | business-validation:148 | correction | Bango "4×"→衍生计算标注 |
| C-20 | business-validation:154 | correction | market-positioning"$20-200 真空"引述→伪造引用更正 |
| C-21 | business-validation:179 | correction | R1-R13 硬扫→L0 门控 F1-F4/C1-C6/X1 |
| C-22 | business-validation:182 | correction | R5 独立审查 0 缺陷→自检通过、证据有限 |
| C-23 | business-validation:198 | correction | R1-R13 扫描→L0 门控 F1-F4/C1-C6/X1 |
| C-24 | business-validation:210 | correction | 证据表 deliverables/ zip→不存在[未验证] |
| C-25 | business-validation:211 | correction | 663 提交/10 天 150→665/151 |
| C-26 | business-validation:223 | correction | 证据表 GVR CI→[来源未验证] |
| C-27 | business-validation:224 | correction | 证据表 GVR AI Agents→部分确证注记 |
| C-28 | business-validation:225 | correction | 证据表 DNR 2026/16%→DNR 2025/18% |
| C-29 | business-validation:228 | correction | 证据表 Bango 4×→衍生标注 |
| C-30 | business-validation:259 | correction | 方向 1 R1-R13 硬扫→L0 门控 |
| C-31 | dev-roadmap:13 | correction | 663 commits→665 |
| C-32 | dev-roadmap:14 | verified-correct (keep) | 130 场景与磁盘一致，保持不动（README/AGENTS 129 为过时侧） |
| C-33 | dev-roadmap:17 | correction | demo zip/deliverables/→不存在[未验证] |
| C-34 | dev-roadmap:25 | correction | R1-R13 硬扫→L0 门控 F1-F4/C1-C6/X1 |
| C-35 | dev-roadmap:27 | correction | 01-QA-GATES 现状注记：全仓零引用，全新建 |
| C-36 | dev-roadmap:33 | correction | `_rejected/`→`06-REJECTED/` + manifest.json rejected 键 |
| C-37 | dev-roadmap:41 | correction | "8 模板全部加上"→逐模板精确矩阵 |
| C-38 | dev-roadmap:54 | correction | CLI 动词决策：新增 `validation` 组，`validate` 不复用 |
| C-39 | dev-roadmap:61 | correction | free 层需 schema 扩展（3 字段）+ 定价硬编码 $0/$29 |
| C-40 | dev-roadmap:64 | correction | billing 只读→需新增 create |
| C-41 | dev-roadmap:65 | correction | check_access 错误→FREE_TIER_LIMIT 在生成/调度层抛出 |
| C-42 | dev-roadmap:79 | correction | mvp/ 须 gitignore（运行时产物） |
| C-43 | dev-roadmap:90 | correction | 只读 server 排除 run_validation_scenario |
| C-44 | dev-roadmap:101 | correction | medical seed 现状：7 源/6 topics，缺 extract_fields |
| C-45 | dev-roadmap:102 | correction | financial seed 现状：11 源/5 topics、无 Yahoo Finance |

---

## A/B. 商业论证报告修正项（docs/dev/autoinfo-business-validation-20260902.md）

### C-01 | business-validation L4 | R5 状态表述（header）

- 文件: docs/dev/autoinfo-business-validation-20260902.md:4
- 原文: demo 交付包 R5(1) 通过独立审查、周迭代（最近 10 天 150 提交）
- 新文: demo 交付包 R5(1) 自检通过（[已修正 2026-09-04] 独立审查报告未存档，见 docs/demo-release-standard.md:12）、周迭代（最近 10 天 150 提交）
- 证据: docs/demo-release-standard.md:12（仅自检勾选行，无审查报告存档）；draft:40（finding 8）
- 值变更: "通过独立审查" → "自检通过；独立审查报告未存档"

### C-02 | business-validation L22 | 提交数

- 文件: docs/dev/autoinfo-business-validation-20260902.md:22
- 原文: **663 提交，最近 10 天 150 提交**（高速迭代中）
- 新文: **[已修正 2026-09-04] 665 提交，最近 10 天 151 提交**（高速迭代中）
- 证据: `git rev-list --count HEAD` = 665（2026-09-04 实测）；draft:33（finding 1：663 过时，偏差 2 属自然增长；10 天窗口实测 151）
- 值变更: 663 → 665；150 → 151

### C-03 | business-validation L27 | demo 交付包不存在

- 文件: docs/dev/autoinfo-business-validation-20260902.md:27
- 原文: `autoinfo-demo-package-20260902-perfect2.zip`（**437 文件，4 域 × 24 产物，全溯源**） | deliverables/
- 新文: [已修正 2026-09-04] **[未验证]** `autoinfo-demo-package-20260902-perfect2.zip`（437 文件，4 域 × 24 产物）在仓库与本机均不存在，`deliverables/` 目录不存在；最近似实际交付物：`outputs/autoinfo-deliverable-13domains-20260810.zip`（处置待 todo 2 裁决）
- 证据: repo + $HOME 全盘无此文件、无 deliverables/ 目录；`outputs/autoinfo-deliverable-13domains-20260810.zip` 实测存在（os.path.exists=True）；draft:39（finding 7）
- 值变更: "zip 存在于 deliverables/" → "文件与目录均不存在[未验证]；最近似 outputs/autoinfo-deliverable-13domains-20260810.zip"

### C-04 | business-validation L28 | R5 审查证据缺失

- 文件: docs/dev/autoinfo-business-validation-20260902.md:28
- 原文: **R5(1) 通过独立全量审查，0 P0/P1/P2** | docs/demo-release-standard.md
- 新文: **R5(1) 自检"通过"（0 P0/P1/P2）——[已修正 2026-09-04] 独立全量审查报告未存档（全仓无 R5 报告文件），证据不足** | docs/demo-release-standard.md:12（自检行，非审查报告）
- 证据: docs/demo-release-standard.md:6-12（标准 1 自身要求"审查报告归档"，:12 仅为勾选行）；draft:40（finding 8）
- 值变更: "通过独立全量审查" → "自检通过；审查报告未存档（DoD 标准 1 证据缺失）"

### C-05 | business-validation L53 | TLDR 与 Pragmatic Engineer 定价混用

- 文件: docs/dev/autoinfo-business-validation-20260902.md:53
- 原文: （TLDR 1.25M 订阅、Pragmatic Engineer $15/月）
- 新文: （[已修正 2026-09-04] TLDR 主版 ~1.25M 订阅、免费/广告模式；Pragmatic Engineer $15/月 为独立付费 newsletter——两者定价模式不同，不可混用）
- 证据: librarian bg_af507484 V5（draft:65）：TLDR 免费/广告，PE $15/月确证但与 TLDR 无关
- 值变更: "TLDR 1.25M 订阅、PE $15/月"（并列暗示同模式）→ 拆分标注两种定价模式

### C-06 | business-validation L63 | Reddit 引语转述（1/2）

- 文件: docs/dev/autoinfo-business-validation-20260902.md:63
- 原文: Reddit r/rss "drowning in feeds / +999 unread"
- 新文: [已修正 2026-09-04] Reddit r/rss 多帖（社区情绪转述非逐字引语；thread 1jrh66h "2876 unread" 为可查实例）
- 证据: librarian bg_af507484 V10（draft:70）：情绪真实（thread 1jrh66h），具体引语无法逐字定位
- 值变更: 逐字引语标注 → 转述标注 + 可查实例

### C-07 | business-validation L64 | Reddit 引语转述（2/2）

- 文件: docs/dev/autoinfo-business-validation-20260902.md:64
- 原文: Reddit "once I add more than 3 sources, it becomes unmanageable"
- 新文: [已修正 2026-09-04] Reddit r/rss（社区情绪转述，"3 源即崩"类引语无法逐字定位）
- 证据: librarian bg_af507484 V10（draft:70）
- 值变更: 逐字引语标注 → 转述标注

### C-08 | business-validation L82 | AlphaSense 定价口径混用

- 文件: docs/dev/autoinfo-business-validation-20260902.md:82
- 原文: **$15K-$20K/座席/年**（SMB $12,210/年, Enterprise $123,760/年）| elevatedsignal.com + spendhound + vendr
- 新文: [已修正 2026-09-04] **$15K-$20K/座席/年**（SMB $12,210/年, Enterprise $123,760/年；溯源注释：$12,210/$123,760 可溯源至 SpendHound，Vendr 中位 $17.5K 为合同总额非座席价——per-seat 与合同总额口径不同）| elevatedsignal.com + spendhound + vendr
- 证据: librarian bg_19726af2 P6（draft:82）；官方无公开价目
- 值变更: per-seat 与合同总额混用 → 加口径溯源注释

### C-09 | business-validation L84 | Readless 无永久 Free 层

- 文件: docs/dev/autoinfo-business-validation-20260902.md:84
- 原文: Free / Pro $4.90 / Max $9/月（新玩家，2026）| readless.app/pricing
- 新文: [已修正 2026-09-04] 无永久免费层（仅 7 天免费试用）/ Pro $4.90 / Max $9/月（新玩家，2026）| readless.app/pricing
- 证据: librarian bg_19726af2 P3（draft:79）：Pro $4.90/Max $9 确证，无永久 Free 层
- 值变更: "Free"（永久免费层）→ "仅 7 天试用"

### C-10 | business-validation L85 | Competely 漏 $99 档

- 文件: docs/dev/autoinfo-business-validation-20260902.md:85
- 原文: $39-$59/月起（公开定价）| competely.ai
- 新文: [已修正 2026-09-04] $39 / $59 / $99 三档（公开定价；原记录漏 $99 Scale 档）| competely.ai
- 证据: librarian bg_19726af2 P4（draft:80）
- 值变更: "$39-$59/月" → "$39/$59/$99 三档"

### C-11 | business-validation L115 | BlogWatcher 仓库误标

- 文件: docs/dev/autoinfo-business-validation-20260902.md:115
- 原文: anthropics/skills 官方仓库 | **BlogWatcher skill**（RSS 监控）已在 KiwiClaw/OpenClaw 生态存在
- 新文: [已修正 2026-09-04] 社区/生态 skill 仓库（anthropics/skills 官方仓库无 BlogWatcher/rss skill） | **BlogWatcher skill**（RSS 监控）已在 KiwiClaw/OpenClaw/Hermes 生态存在（KiwiClaw Hub + OpenClaw registry + Hermes blogwatcher-cli v2.0.0）
- 证据: librarian bg_af507484 V6/V7（draft:66-67）：anthropics/skills 全量列表无 blogwatcher/rss 技能；KiwiClaw/OpenClaw/Hermes 均存在
- 值变更: 检查项"anthropics/skills 官方仓库" → "社区/生态 skill 仓库（anthropics/skills 无此 skill）"

### C-12 | business-validation L125 | changedetection.io "DIY" 措辞误导（4.2 表）

- 文件: docs/dev/autoinfo-business-validation-20260902.md:125
- 原文: ✅ changedetection.io $8.99/月 + MCP = DIY 监控
- 新文: ✅ [已修正 2026-09-04] changedetection.io（自托管开源版免费；$8.99/月为托管 SaaS 价）+ MCP = DIY 监控
- 证据: librarian bg_19726af2 P10（draft:86）：$8.99 精确（官方首页）但自托管 OSS 免费，$8.99 为 hosted SaaS
- 值变更: "$8.99/月 DIY" → "自托管免费 / SaaS $8.99/月"

### C-13 | business-validation L127 | R1-R13 术语错误（4.2 表）

- 文件: docs/dev/autoinfo-business-validation-20260902.md:127
- 原文: **强（R1-R13 硬扫 + G0-G5）**
- 新文: **强（[已修正 2026-09-04] L0 门控 F1-F4/C1-C6/X1 硬扫 + G0-G5）**
- 证据: scripts/quality_gate.py:14-64（F1-F4 格式层 / C1-C5 内容层 / G6 / X1 跨产品 = L0 gate 检查集）；R1-R13 仅存在于 src/autoinfo/mcp/scenarios/regression/regression-product-quality-all-templates.yaml（LLM 规则子集，非"硬扫"）；draft:41（finding 9）
- 值变更: "R1-R13 硬扫" → "L0 门控 F1-F4/C1-C6/X1 硬扫"

### C-14 | business-validation L133 | changedetection.io "DIY" 措辞误导（4.3 正文）

- 文件: docs/dev/autoinfo-business-validation-20260902.md:133
- 原文: **监控核心已经被 DIY 化（$8.99/月 changedetection.io）**。
- 新文: **监控核心已经被 DIY 化（[已修正 2026-09-04] changedetection.io：自托管开源版免费，$8.99/月为托管 SaaS 价）**。
- 证据: librarian bg_19726af2 P10（draft:86）
- 值变更: "$8.99/月 DIY 化" → "自托管免费 / SaaS $8.99/月"

### C-15 | business-validation L135 | R1-R13 + D1-D5 双重术语错误

- 文件: docs/dev/autoinfo-business-validation-20260902.md:135
- 原文: 不会默认做 R1-R13 硬扫（空壳/泄漏/占位/品牌残留）+ D1-D5 付费价值维度
- 新文: 不会默认做 [已修正 2026-09-04] L0 门控 F1-F4/C1-C6/X1 硬扫（空壳/泄漏/占位/品牌残留）+ D1-D3 交付门控
- 证据: scripts/quality_gate.py:14-64；docs/dev/specs/quality-gates.md:25-27（现行交付门控为 D1-D3，D1-D5 是已归档 launch-validation-framework 旧维度）；draft:41-42（findings 9/10）
- 值变更: R1-R13 → L0 门控 F1-F4/C1-C6/X1；D1-D5 → D1-D3

### C-16 | business-validation L145 | GVR 竞争情报市场数字未验证

- 文件: docs/dev/autoinfo-business-validation-20260902.md:145
- 原文: **$823.4M (2026) → $3,004.1M (2033)，CAGR 20.3%** | Grand View Research
- 新文: [已修正 2026-09-04] **[来源未验证]** $823.4M(2026)→$3,004.1M(2033) CAGR 20.3% 无法定位 GVR 原始报告（$823.4M 与 GVR 无关的 stick-packaging 报告数字撞车）；真实 CI 市场报告区间约 $0.5-19B、CAGR 9-13% | [未验证]（原标 Grand View Research）
- 证据: librarian bg_af507484 V1（draft:61）：GVR 无此报告；全部真实 CI 市场报告在 $0.5-19B / CAGR 9-13%
- 值变更: "GVR $823.4M→$3,004.1M CAGR 20.3%" → "[来源未验证]"（保留定性结论"市场在增长"）

### C-17 | business-validation L146 | GVR AI Agent 市场 2026 基值不符

- 文件: docs/dev/autoinfo-business-validation-20260902.md:146
- 原文: **$10.9B (2026) → $182.9B (2033)，CAGR 49.6%** | Grand View Research
- 新文: [已修正 2026-09-04] **$182.97B (2033) + CAGR 49.6% 已确证；2025 基值实际 $7.63B，"$10.9B (2026)" 非 GVR 原文** | Grand View Research（部分确证）
- 证据: librarian bg_af507484 V2（draft:62）
- 值变更: "$10.9B (2026)" → "2025 基值 $7.63B（2026 基值未证实）；2033/CAGR 确证保留"

### C-18 | business-validation L147 | DNR 付费率口径错误

- 文件: docs/dev/autoinfo-business-validation-20260902.md:147
- 原文: **仅 16%** 全球为数字新闻付费（弱付费基础）| Reuters Institute DNR 2026
- 新文: [已修正 2026-09-04] **18%**（Reuters DNR 2025：20 个较富裕国家篮子，无"全球"口径；16% 为 2019 旧美国数字）（弱付费基础定性结论保留）| Reuters Institute DNR 2025
- 证据: librarian bg_af507484 V3（draft:63）：DNR 2025 = 18%
- 值变更: "16% 全球 / DNR 2026" → "18% / DNR 2025 / 20 国篮子"

### C-19 | business-validation L148 | Bango "4×" 为衍生

- 文件: docs/dev/autoinfo-business-validation-20260902.md:148
- 原文: AI 用户平均付 **4× 订阅费（$66/月）**；67% 称 AI 订阅"最重要" | Bango 2025（market-positioning 引用）
- 新文: AI 用户平均 **$66/月（4 个 AI 工具均摊）**；67% 称 AI 订阅"最重要"；[已修正 2026-09-04] "4× 平均订阅支出"为报告衍生计算，非 Bango 材料原文 | Bango 2025（$66/月与 67% 确证；4× 衍生）
- 证据: librarian bg_af507484 V4（draft:64）：$66/月（4 工具均摊）与 67% 确证；"4×" 不在 Bango 材料里
- 值变更: "4× 订阅费（$66/月）" → "$66/月（4 工具均摊）；4× 为衍生计算标注"

### C-20 | business-validation L154 | market-positioning 伪造引用更正

- 文件: docs/dev/autoinfo-business-validation-20260902.md:154
- 原文: **项目自带 market-positioning.md 说"$20-200/月中间地带真空，只有 Kompyte"——这个论断已经过时**
- 新文: **[已修正 2026-09-04] market-positioning.md 并无"$20-200/月中间地带真空，只有 Kompyte"论断（原报告引述有误）：$20-$200/user/mo 在该文档中为企业 Copilot/IDE WTP 范围（docs/dev/specs/market-positioning.md:144），与"中间地带真空"无关。** 2026 实测发现 Readless（$4.9-9/月 AI digest）、Competely（$39/月竞品监控）、Parano（€89/月）进入了自服务监控区间（"中间价已拥挤"的定性结论保留）
- 证据: docs/dev/specs/market-positioning.md:144（"Enterprise: $20-$200/user/mo (Copilot, IDE plugins)"，全文无"中间地带真空/只有 Kompyte"论断）；draft:44（finding 12）
- 值变更: 伪造引用"market-positioning 说…真空只有 Kompyte" → "该文档无此论断；$20-200 为企业 Copilot/IDE WTP"

### C-21 | business-validation L179 | R1-R13 术语错误（优势 2）

- 文件: docs/dev/autoinfo-business-validation-20260902.md:179
- 原文: R1-R13 硬扫 + G0-G5 + 130 validation 场景
- 新文: [已修正 2026-09-04] L0 门控 F1-F4/C1-C6/X1 硬扫 + G0-G5 + 130 validation 场景
- 证据: scripts/quality_gate.py:14-64；draft:41
- 值变更: "R1-R13 硬扫" → "L0 门控 F1-F4/C1-C6/X1 硬扫"

### C-22 | business-validation L182 | R5 优势表述证据强度

- 文件: docs/dev/autoinfo-business-validation-20260902.md:182
- 原文: R5 独立审查 0 缺陷（可信度证据）
- 新文: [已修正 2026-09-04] R5 自检"通过"（0 P0/P1/P2）——独立审查报告未存档，证据强度有限（可信度证据需补档）
- 证据: docs/demo-release-standard.md:12；draft:40（finding 8）
- 值变更: "R5 独立审查 0 缺陷" → "R5 自检通过；审查报告未存档"

### C-23 | business-validation L198 | R1-R13 术语错误（迭代决策 5）

- 文件: docs/dev/autoinfo-business-validation-20260902.md:198
- 原文: demo 里强化 R1-R13 扫描的可视化
- 新文: demo 里强化 [已修正 2026-09-04] L0 门控 F1-F4/C1-C6/X1 扫描的可视化
- 证据: scripts/quality_gate.py:14-64；draft:41
- 值变更: "R1-R13 扫描" → "L0 门控 F1-F4/C1-C6/X1 扫描"

### C-24 | business-validation L210 | 证据表第 5 行 demo 包不存在

- 文件: docs/dev/autoinfo-business-validation-20260902.md:210
- 原文: deliverables/autoinfo-demo-package-20260902-perfect2.zip | demo 包内容（437 文件）
- 新文: [已修正 2026-09-04] ~~deliverables/autoinfo-demo-package-20260902-perfect2.zip~~（文件与 deliverables/ 目录均不存在；最近似：outputs/autoinfo-deliverable-13domains-20260810.zip，处置待 todo 2 裁决） | demo 包内容（437 文件，未验证）
- 证据: draft:39（finding 7）；os.path.exists 实测
- 值变更: 证据"存在的交付包" → "文件不存在[未验证]"

### C-25 | business-validation L211 | 证据表第 6 行提交数

- 文件: docs/dev/autoinfo-business-validation-20260902.md:211
- 原文: 迭代速度（663 提交/10 天 150）
- 新文: 迭代速度（[已修正 2026-09-04] 665 提交/10 天 151）
- 证据: `git rev-list --count HEAD` = 665（2026-09-04 实测）；draft:33-34（findings 1/2）
- 值变更: 663 → 665；150 → 151

### C-26 | business-validation L223 | 证据表第 18 行 GVR CI

- 文件: docs/dev/autoinfo-business-validation-20260902.md:223
- 原文: Grand View Research：竞争情报工具市场 | $823.4M→$3,004.1M, CAGR 20.3%
- 新文: [已修正 2026-09-04] Grand View Research：竞争情报工具市场 | [来源未验证]（$823.4M→$3,004.1M CAGR 20.3% 无法定位 GVR 原始报告）
- 证据: librarian bg_af507484 V1（draft:61）
- 值变更: GVR 引用 → [来源未验证]

### C-27 | business-validation L224 | 证据表第 19 行 GVR AI Agents

- 文件: docs/dev/autoinfo-business-validation-20260902.md:224
- 原文: Grand View Research：AI Agents 市场 | $10.9B→$182.9B, CAGR 49.6%
- 新文: [已修正 2026-09-04] Grand View Research：AI Agents 市场 | 2033 $182.97B + CAGR 49.6% 确证；2025 基值 $7.63B（$10.9B@2026 非 GVR 原文）
- 证据: librarian bg_af507484 V2（draft:62）
- 值变更: $10.9B(2026) → 2025 基值 $7.63B（部分确证注记）

### C-28 | business-validation L225 | 证据表第 20 行 DNR

- 文件: docs/dev/autoinfo-business-validation-20260902.md:225
- 原文: Reuters Institute DNR 2026 | 16% 全球数字新闻付费率
- 新文: [已修正 2026-09-04] Reuters Institute DNR 2025 | 18%（20 个较富裕国家篮子，非全球口径）
- 证据: librarian bg_af507484 V3（draft:63）
- 值变更: "DNR 2026 / 16% 全球" → "DNR 2025 / 18% 国家篮子"

### C-29 | business-validation L228 | 证据表第 23 行 Bango

- 文件: docs/dev/autoinfo-business-validation-20260902.md:228
- 原文: AI 用户付 4× 订阅费 $66/月
- 新文: [已修正 2026-09-04] AI 用户 $66/月（4 个 AI 工具均摊）；"4×"为报告衍生计算非 Bango 原文
- 证据: librarian bg_af507484 V4（draft:64）
- 值变更: "4× 订阅费" → "$66/月（4 工具均摊）；4× 衍生标注"

### C-30 | business-validation L259 | R1-R13 术语错误（方向 1 表）

- 文件: docs/dev/autoinfo-business-validation-20260902.md:259
- 原文: 展示 R1-R13 硬扫差异
- 新文: 展示 [已修正 2026-09-04] L0 门控 F1-F4/C1-C6/X1 硬扫差异
- 证据: scripts/quality_gate.py:14-64；draft:41（finding 9 估记行 247，实测当前磁盘行号 259）
- 值变更: "R1-R13 硬扫" → "L0 门控 F1-F4/C1-C6/X1 硬扫"

---

## D. 开发路线图修正项（docs/dev/autoinfo-dev-roadmap-20260902.md）

### C-31 | dev-roadmap L13 | 提交数

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:13
- 原文: 663 commits / 247 测试文件
- 新文: [已修正 2026-09-04] 665 commits / 247 测试文件
- 证据: `git rev-list --count HEAD` = 665（2026-09-04 实测）；draft:33（finding 1）
- 值变更: 663 → 665

### C-32 | dev-roadmap L14 | 场景数 verified-correct

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:14
- 原文: | Validation 场景 | 130（65 功能 + 65 回归）| `src/autoinfo/mcp/scenarios/` |
- 新文: | Validation 场景 | 130（65 功能 + 65 回归）[已修正 2026-09-04]（verified-correct, keep：2026-09-04 磁盘实测 = 130 个场景 yaml——主目录 65 功能 + regression/ 65 回归全带 regression:true；README/AGENTS.md 的 129 为过时侧，本报告 130 与磁盘一致，保持不动）| `src/autoinfo/mcp/scenarios/` |
- 证据: on-disk 实测（src/autoinfo/mcp/scenarios/ 主目录 65 + regression/ 65）；draft:36（finding 4）；AGENTS.md 状态表"130 scenarios (65 functional + 65 regression)"
- 值变更: 无（130 → 130，verified-correct, keep — README/AGENTS.md 129 才是待修侧，不在本清单范围）
- 类型: verified-correct (keep)

### C-33 | dev-roadmap L17 | demo 包不存在

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:17
- 原文: R5(1) 通过独立审查，437 文件 4 域 24 产物 | `deliverables/`
- 新文: R5(1) 自检通过（审查报告未存档，见商业报告 C-04）；[已修正 2026-09-04] `autoinfo-demo-package-20260902-perfect2.zip`（437 文件 4 域 24 产物）不存在——`deliverables/` 目录不存在，最近似实际交付物 outputs/autoinfo-deliverable-13domains-20260810.zip（处置待 todo 2 裁决） | outputs/（原 `deliverables/` 路径不存在）
- 证据: draft:39（finding 7）；os.path.exists 实测；docs/demo-release-standard.md:12
- 值变更: "zip 存在（deliverables/）+ 通过独立审查" → "文件不存在[未验证] + 自检通过、报告未存档"

### C-34 | dev-roadmap L25 | R1-R13 术语错误

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:25
- 原文: 质量门控（R1-R13 硬扫 + G0-G5）是唯一不可复制的护城河
- 新文: 质量门控（[已修正 2026-09-04] L0 门控 F1-F4/C1-C6/X1 硬扫 + G0-G5）是唯一不可复制的护城河
- 证据: scripts/quality_gate.py:14-64；draft:41（finding 9）
- 值变更: "R1-R13 硬扫" → "L0 门控 F1-F4/C1-C6/X1 硬扫"

### C-35 | dev-roadmap L27 | 01-QA-GATES 全新建注记

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:27
- 原文: 新增 `01-QA-GATES/` 目录，每次生成 PROCESSED 产物时输出一份 **gate 通过报告**
- 新文: 新增 `01-QA-GATES/` 目录（[已修正 2026-09-04] 现状注记：当前 `scripts/validation_delivery.py` 交付包仅含 01-RAW/02-PROCESSED/03-KB/04-MATRIX/06-REJECTED + validation-report.md + manifest.json，`01-QA-GATES` 全仓零引用——本任务为全新建而非补强），每次生成 PROCESSED 产物时输出一份 **gate 通过报告**
- 证据: scripts/validation_delivery.py:11-13（包结构注释：01-RAW…06-REJECTED + manifest.json）；draft:49（finding 15）
- 值变更: "补强已有结构" 隐含 → "全新建"（明确现状包结构）

### C-36 | dev-roadmap L33 | `_rejected/` 路径措辞错误

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:33
- 原文: 被拒条目（`_rejected/`）与 gate 报告一致（可追溯）
- 新文: [已修正 2026-09-04] 被拒条目（交付包层为 `06-REJECTED/` 目录 + `manifest.json` 的 rejected 记录；`_rejected/` 并非交付包内路径——process 层失败目录为 `collections/<domain>/_failed/`）与 gate 报告一致（可追溯）
- 证据: scripts/validation_delivery.py:11-13, :996, :1015（`rej_dir = stage / "06-REJECTED"`，manifest.json 含 rejected）；draft:49（finding 15）
- 值变更: `_rejected/` → `06-REJECTED/` 目录 + manifest.json rejected 键（并澄清 process 层 `collections/<domain>/_failed/`）

### C-37 | dev-roadmap L41 | 8 模板溯源现状精确矩阵

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:41
- 原文: 8 个 product template 全部加上（现在是部分有）
- 新文: [已修正 2026-09-04] 逐模板精确矩阵（替代笼统的"8 个全部加上"）：report(md/html)/premium-briefing/enterprise-briefing 已有完整 References 区块（保持）；column 正文有"full source list in References"字样但模板缺 References 区块（bug，需补区块）；digest/presentation 有行内 (Source: url) 无聚合尾区块（需加聚合区块）；tutorial 已有行内 (Source: url) + Further Reading（需补 Sources 聚合区块）；magazine-digest 无 Sources 区块（需加）
- 证据: draft:50（finding 16，codegraph output/__init__.py 现状枚举：PRODUCT_TEMPLATES 8 行 output/__init__.py:1816-1865；tutorial 行内 cite prompt）
- 值变更: "8 个全部加上（部分有）" → 8 模板逐一现状与动作矩阵

### C-38 | dev-roadmap L54 | CLI 命令动词决策记录

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:54
- 原文: CLI `autoinfo validation list --summary` 输出分组统计（功能 65 / 回归 65）
- 新文: CLI `autoinfo validation list --summary` 输出分组统计（功能 65 / 回归 65）[已修正 2026-09-04] 命令动词决策注记——新增 `autoinfo validation` 命令组承载本命令；现有 `autoinfo validate` 是 matrix/diff/stability 执行器，不复用不混用
- 证据: draft:51（finding 17：现有 validate CLI 为 matrix/diff/stability，validate.py）；src/autoinfo/mcp/validation.py:901-922（`list_scenarios()` 已返回 name/category/regression/requires_env/requires_http/matrix_domains——MCP 侧增量小，CLI 为主要增量）
- 值变更: 无动词裁决记录 → 明确"新 `validation` 组 / `validate` 执行器不混用"决策

### C-39 | dev-roadmap L61 | free 层 schema 扩展 + 定价硬编码现状

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:61
- 原文: `subscription` tier 配置里加 free 层默认值（当前"prices are placeholders"）
- 新文: `subscription` tier 配置里加 free 层默认值（当前"prices are placeholders"）[已修正 2026-09-04] 现状精确化——免费层限制需 schema 扩展（max_products / max_frequency / allow_custom 三字段，当前无任何强制 quota）；定价确为占位/硬编码：storefront `_PRODUCT_PRICING` raw=free/$0、processed=premium/$29（src/autoinfo/api/storefront.py:55-68）
- 证据: src/autoinfo/api/storefront.py:55-68（实测 price_monthly 0.0/29.0）；draft:52（finding 18）
- 值变更: "加默认值"（笼统）→ "schema 扩展 3 字段 + 定价硬编码现状 $0/$29"

### C-40 | dev-roadmap L64 | billing CLI 需新增 create

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:64
- 原文: `autoinfo billing` CLI 能创建 free 订阅并正确 gate（超过限制被挡）
- 新文: `autoinfo billing` CLI 能创建 free 订阅并正确 gate（超过限制被挡）[已修正 2026-09-04] 现状注记：当前 `autoinfo billing` 仅有只读 summary 命令，无 create——新增订阅创建能力是本任务的真实增量
- 证据: draft:52（finding 18：billing 现为只读）；README CLI 表（billing summary 为唯一子命令）
- 值变更: "能创建"（假定已有）→ 明确"当前只读，create 为新增"

### C-41 | dev-roadmap L65 | check_access 错误语义澄清

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:65
- 原文: `check_access()` 对 free 层超出限制返回明确错误（不是静默）
- 新文: [已修正 2026-09-04] free 层超出限制在生成/调度层抛出显式 `FREE_TIER_LIMIT` 错误（不是静默）；`check_access()` 保持布尔判定语义不变——限额执行不塞进布尔 fast path
- 证据: draft:52（finding 18：check_access() 为布尔判定）；docs/dev/specs/quality-gates.md（envelope 错误码惯例）
- 值变更: "check_access 返回明确错误" → "FREE_TIER_LIMIT 显式错误在生成/调度层；check_access 保持布尔"

### C-42 | dev-roadmap L79 | mvp/ 目录须 gitignore

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:79
- 原文: 自动：生成 `mvp/` 交付目录（产物 + gate 报告 + 溯源 + 用户联系方式占位）
- 新文: 自动：生成 `mvp/` 交付目录（产物 + gate 报告 + 溯源 + 用户联系方式占位）[已修正 2026-09-04] 约束注记：`mvp/` 为运行时产物目录，须加入 .gitignore（同 collections//outputs/ 纪律）；且含终端用户联系方式/PII，禁止提交仓库
- 证据: AGENTS.md Runtime Artifacts 表（mvp/ 属运行时产物类）；draft:53（finding 19：N1 全新建）
- 值变更: 无 gitignore/PII 约束 → 明确 gitignore + PII 约束

### C-43 | dev-roadmap L90 | 只读 server 工具集需排除执行类工具

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:90
- 原文: 暴露工具：`search_knowledge_base`（只读）、`get_kb_entry`、`export_kb(format=agent)`、`list_validation_scenarios`
- 新文: 暴露工具：`search_knowledge_base`（只读）、`get_kb_entry`、`export_kb(format=agent)`、`list_validation_scenarios` [已修正 2026-09-04] 边界注记：白名单必须排除执行类工具（尤其 `run_validation_scenario` 可触发真实 collect/process 副作用，与"只读"承诺冲突）；暴露的 4 个工具均已实现，工作量=只读 server 封装/白名单
- 证据: draft:54（finding 20：server.py 全部 146 工具，无只读子集封装；4 工具已实现）
- 值变更: 工具清单未提执行类排除 → 明确排除 run_validation_scenario 等执行类工具

### C-44 | dev-roadmap L101 | medical seed 现状精确化

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:101
- 原文: `autoinfo domain init medical-research --seed`：一条命令创建域 + 预置 sources（PubMed/OpenAlex/CrossRef）+ 默认 topic 集 + 默认 extraction schema
- 新文: `autoinfo domain init medical-research --seed`：一条命令创建域 + 预置 sources + 默认 topic 集 + 默认 extraction schema [已修正 2026-09-04] 现状精确化：medical-research sources.yaml 已有 7 源（PubMed/Semantic Scholar/arXiv/CrossRef/DBLP/OpenAlex/USPTO）+ 6 组 topics + exclude_keywords——增量主要是默认 extract_fields（该 yaml 现无任何 extract_fields）+ `--seed` 别名（现仅 `domain import --from-demo`），预置源集无需重写
- 证据: src/autoinfo/data/domains/medical-research/sources.yaml 实测（7 源 6 topics，无 extract_fields）；draft:55（finding 21）
- 值变更: "预置 PubMed/OpenAlex/CrossRef 3 源"（低估现状）→ "7 源已在盘上，缺 extract_fields + --seed 别名"

### C-45 | dev-roadmap L102 | financial seed 现状精确化（无 Yahoo Finance）

- 文件: docs/dev/autoinfo-dev-roadmap-20260902.md:102
- 原文: 同上 `financial-intelligence --seed`（SEC EDGAR/Yahoo Finance/Quandl）
- 新文: 同上 `financial-intelligence --seed` [已修正 2026-09-04] 现状精确化：financial-intelligence sources.yaml 已有 11 源（Alpha Vantage/FRED/Finnhub/SEC EDGAR/Twelve Data/World Bank/Quandl/CNBC/TheStreet/MarketWatch/WSJ）+ 5 组 topics——**该域现无 Yahoo Finance 源**（原文括注与盘上配置不符），真实增量同为默认 extract_fields + `--seed` 别名
- 证据: src/autoinfo/data/domains/financial-intelligence/sources.yaml 实测（11 源，无 yahoo 条目，无 extract_fields）；draft:55（finding 21）
- 值变更: "预置 SEC EDGAR/Yahoo Finance/Quandl" → "11 源已在盘上且无 Yahoo Finance；缺 extract_fields 才是真实 delta"

---

## 统计

- 修正项总数: 45（C-01 至 C-45）
- 携带 `[已修正 2026-09-04]` 标记的项: 45/45
- verified-correct (keep) 注记项: 1（C-32，roadmap L14 场景数 130 保持不动）
- 按 target 文件: business-validation 30 项（C-01-C-30）；dev-roadmap 15 项（C-31-C-45）
- 覆盖映射: draft findings 1-22（A 组 22 项硬数据）→ C-01/02/03/04/13/14/15/21/23/30/31/32/33/34/35/36/37/38/39/40/42/43/44/45 等；市场声明 V1-V12 → C-05/06/07/11/16/17/18/19/26/27/28/29；定价 P1-P10 → C-08/09/10/12/14
- 不裁决项: demo zip 处置（C-03/C-24/C-33 仅记录"不存在"发现，todo 2 裁决）
