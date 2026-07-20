# Hermes KnowledgeBase — 基于 Obsidian 的知识库系统

> **位置**：`D:\Hermes-KnowledgeBase\`
> **引擎**：Obsidian + remotely-save 插件（自动同步）
> **规模**：905 篇 `.md` 文件 · 4 级流水线 · 受控关键词表 · Git 版本管理
> **设计原则**：**Raw → Draft → Wiki**，三步递进，不可越级。

---

## 一、为什么不是"记笔记"，是"知识流水线"

传统知识库是"写 → 分类 → 归档"。这个库是：

```
信息摄入 → 脱壳清洗 → 结构化 → 永久入库
   ↓          ↓          ↓          ↓
 00-Inbox   01-Raw    02-Draft   03-Wiki
```

**核心规则**（2026-07-01 用户确认，写进 `_kb-reform-design.md`）：

- 所有入库默认进 **01-Raw**，这是唯一入口
- **Raw → Draft → Wiki 顺序不可跳**，任何时候不能越过中间层
- **Draft → Wiki 只能用户放行**，agent 不得代劳
- **03-Wiki 禁止直接写入**（硬规则）
- 历史遗留的 Wiki 直接写入权限已全部收回

---

## 二、4 级流水线详解

### 00-Inbox —— 电光火石

> 一切信息的第一落点。

临时堆放一切快进快出的信息：安全事件、运行记录、周报草稿等。
**每日清理**——不归档就删。

| 内容 | 举例 |
|:----|:-----|
| 安全告警 | `2026-06-06-ainovel-key-leak.md` |
| 自我复盘 | `self-packaging-reports/` — 每周运行总结 |

**规则**：文件不超过一周生命周期。非永久信息不走 Raw。

---

### 01-Raw —— 原始素材

> 信息脱壳后的"毛坯房"。全量保留，不做取舍。

这是知识库的大胃王——698 篇 `.md`，占总量的 **77%**。

| 子目录 | 文件数 | 来源 |
|:-------|:------:|:-----|
| `GitHub/` | **491** | GitHub 仓库、Issue、PR、文档的原始抓取 |
| `Xpertai/` | **153** | Xpert AI 平台相关 |
| `Bilibili/` | **32** | B 站视频字幕（Whisper 转录后） |
| `Loop-Engineering/` | **10** | Loop Engineering 方法论 |
| 根目录 | 若干 | juejin/zhihu/cnblogs 文章、开发计划等 |

**模板**：`01-Raw/_template_raw.md`

```yaml
---
source_url: ""           # 原始链接（必填）
source_type: ""          # video / article / paper / book / link
source_platform: ""      # bilibili / zhihu / wechat / arxiv / other
author: ""               # 作者名称
fetch_date: "{{date}}"   # 抓取日期
status: raw              # raw / processing / compiled
tags: []                 # 标签列表
priority: 3              # 优先级 1-5（1最高）
language: "zh"
related_concepts: []     # 相关概念（AI 自动提取）
---
```

**规则**：
- 文件名用**主题描述**，不用 BV 号 / juejin ID 等不明编码
- 来源元数据必须完整（`source_url`、`source_type`、`source_platform`）
- 原文全文保留，可以加摘录和解读（在 `## 核心摘录` 和 `## 个人解读` 章节）

---

### 02-Draft —— 半成品

> 从 Raw 中提取、清洗、重组后的草稿。等待人类终审。

37 篇，涵盖 AI-coding、Bilibili、Xpertai 等方向。

| 内容 | 说明 |
|:-----|:-----|
| `Hermes-Agent完全指南-2026开源AI智能体.md` | 对外发布指南 |
| `5-Agent-Skill-Design-Patterns-ADK.md` | ADK 技能设计模式（已进入 03-Wiki） |
| `如何写好一个Skill（一）.md` | 系列教程（已进入 03-Wiki） |
| `从零部署Hermes-Agent安装教程.md` | 安装教程 |

**规则**：
- 只从 01-Raw 来，不直接创建
- 内容经过清洗、合并、转述、结构化
- 等待用户审核 → 放到 03-Wiki（agent 无权执行这一步）

---

### 03-Wiki —— 永久知识

> 审核通过、确认可长期引用的知识资产。

160 篇。包括方法论、教程、概念笔记。

| 内容 | 文件数 |
|:-----|:------|
| `Xpertai/` | 132 |
| `Bilibili/` | 20 |
| 根目录单文件 | `5-Agent-Skill-Design-Patterns-ADK.md`、`Loop-Engineering.md`、`如何写好一个Skill.md` 等 |

**核心文档**（根目录）：
- `hermes-agent-15-技巧-5-心法.md` — Hermes Agent 使用心法
- `ai-assisted-coding-workflow-general-methodology.md` — AI 辅助编码通用方法论
- `goal-programming-autonomous-ai-collaboration.md` — 目标编程与自主 AI 协作
- `harness-工程-多模态视角.md` — Harness 工程的多模态视角
- `b站视频-本地-ai-知识库.md` — 本地 AI 知识库搭建

---

## 三、关键词系统（`_keywords.yaml`）

**位置**：`D:\Hermes-KnowledgeBase\_keywords.yaml`

统一管理全库标签，避免同义不同名。

```yaml
ADK:
  aliases: [ADK]
  category: tool
  status: verified
  related: [AI-Agent, Skill-Design]

AI-Agent:
  aliases: [AI-Agent, AI Agent, Agent, AI, coding-agent]
  category: concept
  status: verified
```

**状态机制**：
- `verified` — 人工确认的标准关键词
- `auto_added` — AI 自动抽取的候选词
- `merged` — 已合并到其他词条
- `deprecated` — 已弃用

**当前**：554 行，覆盖全部核心概念。

---

## 四、自动化工作流

### B 站视频 Ingestion

```
B站链接 → bilibili-subtitle skill (Hermes)
    → Whisper GPU 转写
    → MiniMax 后处理
    → 01-Raw/Bilibili/
    → ingest-raw-to-draft skill (Hermes)
    → 02-Draft/Bilibili/
```

### 网页文章 Ingestion

```
文章链接 → scrapling-ingest / Firecrawl (Hermes)
    → 01-Raw/{source_platform}/
    → ingest-raw-to-draft skill (Hermes)
    → 02-Draft/{subdir}/
```

### 文档本地化（Omni 管线）

```
源文件（DOCX/PDF/PPTX/MD）
    ↓ OPP（标准化 + manifest + 骨架保留）
Intermediate/*.md + *_manifest.json + *.skeleton.zip
    ↓ OL（翻译 + YAML frontmatter）
Output/*_translated.md
```

工具仓库：
- [Omni Pre-Processor](https://github.com/1StepMore/Omni_Pre_Processor)
- [Omni Localizer](https://github.com/1StepMore/Omni_Localizer)

---

## 五、版本控制与同步

| 特性 | 方案 |
|:-----|:-----|
| **版本管理** | Git（仓库根目录有 `.git/`） |
| **云同步** | Obsidian 插件 `remotely-save` |
| **忽略规则** | `.gitignore`（122 字节） |
| **日志** | `logs/` 目录，含 `audit_*.log`、`ol-*.log`、`orf_*.log` |

### 危险操作记录（`logs/`）
- `audit_20260630.log` — 审计日志
- `ol-2026-06-30.log` — 本地化管线日志
- `orf_20260630.log` — 格式转换日志

---

## 六、数据总览

| 层级 | 文件数 | 占比 | 说明 |
|:----|:------:|:----:|:-----|
| 00-Inbox | 8 | 0.9% | 临时信息，周期性清理 |
| 01-Raw | 698 | **77.2%** | 原始素材，知识库的"毛坯层" |
| 02-Draft | 37 | 4.1% | 半成品草稿，待审核 |
| 03-Wiki | 160 | 17.7% | 终审永久知识 |
| **总计** | **905** | 100% | |

### 信息流漏斗

```
外部信息（无限）
    ↓
00-Inbox（临时存储，<1%）
    ↓
01-Raw（698，77%） ←——— 所有信息的第一入口
    ↓ 清洗/结构化
02-Draft（37，4%）  ←——— agent 可处理到此层
    ↓ 人类审核
03-Wiki（160，18%） ←——— 只有用户能放行
```

---

## 七、设计哲学

1. **不追求整洁，追求流速** — Raw 层可以乱，入库必须快
2. **Agent 能写 Draft，不能写 Wiki** — 知识资产的最终裁判是人
3. **文件名要可读** — BV 号 > 标题 > "juejin-762697..."，禁止不可读的 ID 命名
4. **来源不可丢** — 每篇 Raw 必须溯源，将来才能验证和回溯
5. **关键词统一** — 不创造同义词，有 `_keywords.yaml` 统管

---

*生成于 2026-07-20 · 基于 `D:\Hermes-KnowledgeBase\` 最新状态*
