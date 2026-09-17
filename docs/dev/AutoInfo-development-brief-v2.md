# AutoInfo 开发简报

> **性质**：方向简报（由首席助手基于最终发起人的 expectation 形成）
> **用途**：交给 coding agent 核对代码现状 → 由其形成自己的开发方案
> **本简报不含实现路径**——怎么实现由 coding agent 决定
>
> **版本**：**v2**（2026-09-15）— 相对 v1 的实质变更：
> ① 新增「**三·补、RAW 转售边界（合规界定）**」——回应"哪些 tier 允许转售"
> ② §五 修正为**两档**（v1 把终局标准与 demo 标准混列）
>
> ⚠️ 若你手上这份**没有「三·补」、或 §五 未分档** → 那是 v1 旧版。

---

## 零、商业定位（读懂这张卡即可，代码背景你已熟悉）

| 项 | 内容 |
|:--|:--|
| **卖什么** | **rawdata + processdata 都卖**；客户用途自定，我们按诉求定制交付 |
| **卖给谁** | 需要可审计情报的从业者（研究 / 分析 / 投资 / 内容）|
| **当前阶段** | demo——**采集端与生产端真跑通**；不搞付费端等空中楼阁 |
| **商业目标** | **赚钱**（项目为现金流服务，非技术练习）|
| **不做 SaaS 工具** | 与"卖结果"冲突（客户会用工具自己产出，就不买结果）|
| **与 AutoMedia 关系** | 共用部分技术底座，但商业逻辑不同（我们卖"加工结果"）；并行推进 |

---

## 一、Expectation（最终发起人的期望，最高优先）

### 商业模式
**rawdata 和 processdata 两个都卖。**

| 类型 | 是什么 | 客户 |
|:--|:--|:--|
| **rawdata** | 采集的原始信息 | 需要数据自己做分析的人 |
| **processdata** | 加工后的结构化结论 | 需要结论直接用的人 |

### 我们的价值（核心定位）
> **客户提出他的诉求，我们基于他的诉求，为他提供定制化的成果。**

- 客户用途**由客户自己决定**（自媒体 / 学术 research / 商业论证 / 其他）——我们不预设、不判断
- 我们的价值在**按需定制**

### 首个成果
**能对外演示的完整 demo**——**采集端与生产端真跑通**（实际运行层级，非概念演示）。

### 终局形态
**内核（能力本身）+ 私有部署优先**（与 AutoMedia 同一思路），兼容 SaaS 与服务。

### 目标客户（假设）
需要可审计情报的从业者（研究 / 分析 / 投资 / 内容）。

### 时间
**不设时间节点**。持续开发，与 AutoMedia 并行推进。

---

## 二、为什么（商业依据）

| 事实 | 数据来源 | 含义 |
|:--|:--|:--|
| 通用 AI 研究=红海 | 大厂 deep research 全部内置 $20/月档 | ❌ 不做"通用信息入口" |
| 横向层已出清 | 5,600+ AI 初创关门，78% 是 wrapper | ❌ 通用路线死路 |
| **成功案例全靠独特资产** | AlphaSense $700M ARR / Glean $100M+ ARR / Recorded Future $2.65B 被收购 | ✅ **卖结果/数据才是出路** |
| 垂直情报能收高溢价 | AlphaSense $10-20k/席/年 | ✅ 与"卖结果"模式一致 |
| **稀缺能力** | 跨源去重/实体消解、**持续追踪**、**真正可验证性** | ✅ **这三条是我们的机会** |
| 我们的核心能力在大厂优势区 | 聚合 + 结构化 | ⚠️ 必须靠"可验证 + 持续"差异化 |

---

## 三、🎯 目标形态（这两个项目应该成为的样子）

> **这一章是最终目标图景（项目的"应该成为的样子"）。**
> **首个里程碑**：让采集端与生产端在这些形态的框架下**真跑通**（可对外演示的完整 demo）。
> **最终目标**：以下形态**全部达成**。coding agent 应据此形成自己的实现方案。

### 形态 A：每条结论可溯源、可审计

**应该成为的样子**：
- 任意一条结论，都能追溯到**原始信源**（原文片段 + 抓取时间 + 链接）
- 能输出**审计报告**——非技术人员看懂"这个结论为什么可信"
- **明确区分**"原文事实"与"LLM 推论"（不混淆）
- 每条结论能回答：几个来源支持？来源什么等级？有无冲突？

### 形态 B：从"一问一答"到"持续追踪"

**应该成为的样子**：
- 客户可以**设定关注对象**（公司 / 人物 / 话题 / 政策）
- 系统**持续监控**，信息变化时**主动通知**（不是等客户来问）
- 通知里能说明"**哪里变了**"（不只是"有新内容"）
- 能给出关注对象的**时间序列**（历史脉络），而非孤立快照

### 形态 C：按客户诉求定制交付

**应该成为的样子**：
- 不同客户可以配不同的**信源组合 / 主题 / 交付形态**
- 定制发生在**配置层**，内核通用——新增客户不需要改代码
- 客户提出诉求 → 我们能配置出对应的成果（这是我们的核心价值）

### 形态 D：信源质量有保障

**应该成为的样子**：
- **信源分级**（按权威性）
- **交叉验证**（同一事实多源比对）
- **实体消解**（同一实体跨源归一）
- **冲突标记**（信源矛盾时明确标出，不掩盖）
- 整体效果：用公开信源加工出**比拟私有信源**的质量

### 形态 E：多形态交付成为卖点

**应该成为的样子**：
- 已有的 EPUB / 有声书 / 视频等形态，明确定位为**差异化能力**（竞品只给文本）
- 每种形态有明确的使用场景（不是"什么都能输出"，而是"什么场景用什么形态"）

## 三·补、RAW 转售边界（合规界定，2026-09-15 补充）

> **背景**：coding agent 问「哪些 tier 允许转售 RAW」。这是合规/法律判断，代码替代不了。
> **本节的规则即为答复**，可直接作为该项的判定依据。
> ⚠️ **本节不是法律意见。** 正式对外销售前，`licensed` 类源必须由法务/发起人**逐个核对许可证原文**。

### 核心原则：**default-deny（默认不可转售）**

风险不对称决定了默认值：

| 误判方向 | 后果 | 可逆性 |
|:--|:--|:--|
| 误判"可转售" | **侵权**——最高风险，可能致命 | ❌ 不可逆 |
| 误判"不可转售" | **少卖**——事后核实即可放开 | ✅ 可逆 |

**因此：凡未明确证明可转售的，一律按不可转售处理。**

### 🚨 先纠正一个危险前提

把「**部分 RSS**」归入"可转售，需署名"——**这个归类在危险方向上错了**：

> **Reuters 官方条款原文**：*"You may not use the Content or Service, including without limitation, **any Content made available through an RSS feed, in any commercial product**"*

**大批新闻站点的 RSS 明确禁止进入商业产品。**「是 RSS」**不能**作为可转售依据——新闻类 RSS 应**默认视为不可转售**，除非该站条款明确允许。（AP / NYT 同理，已核实其条款明确禁止商业再分发。）

### 转售规则表（按 `tos_classification`）

| 分类 | 转售规则 |
|:--|:--|
| `open` | ✅ **可转售**，须遵守该源的具体署名/许可条件（如 CC-BY 需署名） |
| `licensed` | ❌ **默认不可转售**。`licensed` 的准确含义是「**有协议、条件未定**」，**不是「已授权」**。只有逐条审阅许可证、确认允许再分发后，才可解锁 |
| `restricted` | ❌ 禁止转售 |
| `sensitive` | ❌ 禁止转售 |
| **未分类** | ❌ **禁止转售** ← 现状是"按 tier 自动放行"，**必须反转** |

**⚠️ 关键：`quality_tier` 不能用来推导许可。** 代码现状 `tos_compliant = tos_classification in ("open","licensed")` 把 `licensed` 与 `open` 等同放行——但 `licensed` 是**未知**，不是**可用**。用一个「权威性」字段自动推导「许可」分类在逻辑上不成立——**现有数据里已有 59 例 tier 与显式 tos 断言不一致**（如 `WSJ Markets` / `nyt` / `ap-api` / `wanfang` 都是 tier=1 却实际 licensed；反向也大量存在）。

### 可转售源清单（**demo 域 medical-research**，逐个已核实官方来源）

| 源 | 官方许可事实（已核实） | 可转售 |
|:--|:--|:--|
| **OpenAlex** | 官方：*"Our data is free and reusable under a **CC0** license"* | ✅ **可** |
| **DBLP** | 官方：*"All data … publicly available for reuse under the **CC0 1.0** Public Domain Dedication"* | ✅ **可** |
| **SEC EDGAR** | SEC 官方 FAQ：*"All Government-created content on sec.gov and EDGAR public filing content are **free to access and reuse**"* | ✅ **可** |
| **CrossRef** | 官方：*"Almost all of the metadata we hold is **reusable without restriction**, with the exception of **abstracts** which are subject to publisher or author copyright"*；多数元数据为 public domain (CC0) | ✅ **元数据可**<br>⚠️ **摘要不可**（须单独判定） |
| **USPTO / PatentsView** | *"the published material is in the **public domain and may be freely distributed and copied**"* | ✅ **可**（附条款细则） |
| **PubMed / MEDLINE 元数据** | NLM：数据可下载，但须遵守 NLM Terms——**"acknowledge NLM as the source"** | ✅ **可，但必须署名 NLM** |
| **arXiv** | 官方：默认 *"arXiv perpetual, **non-exclusive license** … also **limits re-use of any type** from other entities or individuals"*；仅作者显式选 CC 的论文开放 | ❌ **默认不可**（仅个别 CC 论文可） |
| **Semantic Scholar** | AI2 专门 API 协议；同类语义学者数据协议明示禁止 *"transfer, sell, rent, lease, **commercialize**, lend, distribute, or sublicense the Data"* | ❌ **默认不可**（须读 API 协议） |
| **PMC 全文** | NLM：*"The **majority** of the articles in PMC are subject to **traditional copyright restrictions** … not Open Access"*；仅 **PMC OA Subset** 为 CC 许可 | ⚠️ **仅 OA Subset 可** |

> **该域小结**：**可转售** = OpenAlex / DBLP / SEC EDGAR / CrossRef(元数据) / USPTO / PubMed(元数据，须署名 NLM)；**默认不可** = arXiv / Semantic Scholar；**仅子集可** = PMC（OA Subset）。

### 判定依据（供 coding agent 参考，实现由其决定）

判定字段应表达「**许可是否已核实**」，而不是从 `quality_tier` 推导。**未核实 = 不可转售。**

---

## 四、边界（明确不做）

- ❌ 不做"通用 AI 研究助手"（红海中心）
- ❌ 不追加大厂已有能力（更多信源、更快搜索——大厂随时能复制）
- ❌ 不做 SaaS 工具（**与"卖结果"冲突**：客户会用工具自己产出，就不买结果了）
- ❌ 不增加输出格式数量（已有 7 种）
- ❌ 不为技术洁癖而重构（**重构必须有商业理由**——若现有设计阻碍目标形态达成，那就是商业理由）
- ❌ **未经许可核实的源，不得转售 RAW**（default-deny，见"三·补"）

---

## 五、验收标准

> ⚠️ **本档分两档**。v1 把终局标准与 demo 标准混列，以下为修正版。

### 五·A 首个 demo 验收标准 ← **现在按这一档验收**

- **demo 真跑通**：采集端 + 生产端实际运行
- **RAW 转售边界可判定**：每个源的转售资格有明确依据（"三·补"规则表）

### 五·B 终局验收标准 ← **有客户后逐项达成；不是首个 demo 的门槛**

- **任意一条结论，能在 3 步内追溯到原始信源**原文
- **能输出审计报告**——非技术人员看懂"这个结论为什么可信"
- **能设定关注对象并收到变化通知**（含"哪里变了"），而非只有一次性快照
- **能为不同客户配不同信源组合 + 主题**（定制的核心），不需要改代码

---

## 六、红线

- 现有能力**不得减少**（30 个采集器 / 155+ validation 场景 / 7 种输出形态 / 4 层 KB 管线）
- 任何触及现有能力的改动，需满足"**阻碍赚钱**"判据（阻碍交付 / 阻碍获客 / 阻碍维持），且**逐项批准**
- 底线：项目为赚钱服务；如现有设计确实挡了财路，那是要面对的问题

---

## 附录：现状事实（供核对，非方向指引）

> ⚠️ 以下仅为客观事实描述，**不含任何改造建议**。coding agent 应自行核对并判断。

| 项 | 事实 |
|:--|:--|
| 代码规模 | 217,079 LOC / 467 文件 / 279 测试文件 |
| 采集能力 | **30 个采集器**（PubMed / Semantic Scholar / DBLP / OpenAlex / USPTO / NYT / Yahoo Finance / RSS / Web / webhook / email / PDF / Reddit / Spotify / YouTube / Bilibili / Apple Podcasts / SEC EDGAR / HackerNews / AKShare 等）|
| 质量门 | G0-G5 + D1-D3 交付门 + translation QA 管线 |
| 校验体系 | **155+ validation 场景**（功能 + 回归 + 红队对抗层）|
| 知识库 | 4 层管线（含 git 版本）+ `[[wiki links]]` |
| 检索 | 混合（FTS5 关键词 + sqlite-vec 向量）+ 分面过滤 |
| 输出形态 | Markdown / JSON / PDF / HTML / EPUB / MOBI / 有声书（章节化 MP3）/ 视频（HyperFrames）|
| 域配置 | 已有 `domain.quality_gates`（按域可配置质量门）+ `set_gate_config` / `get_gate_config` 工具 |
| 报告基础 | 已有 `delivery/gate_report.py`（门控报告实现）|
| CLI 实测 | `autoinfo --help` 正常（exit=0）|
