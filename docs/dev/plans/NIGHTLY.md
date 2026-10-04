# NIGHTLY.md — AutoInfo · 「不眠计划」执行面

> **两个区，物理分开，权限不同**：
> - **【冻结区】**（完成定义 + 验收命令）：由 code profile 维护。**coding agent 只读、只跑，不得修改。**
> - **【活区】**（差距矩阵 / 下一步队列 / 摩擦账本 / 修订请求）：由 **coding agent 维护**。
>
> L1 总纲：`Hermes-Workspace/00-Records/dev-assets/NIGHTLY-PLAN-L1.md`
> 冻结区要改 → 只能往活区的「修订请求」写，等 owner / code profile 裁定；期间按原样执行。

---

## 【冻结区】完成定义（DoD）

**生产单元 = 域（21 个）**。一个域**达标 = 下面四条件同时成立**：

| # | 条件 | 判据（可机械计算） |
|:--|:---|:---|
| ① | **真语料** | 该域**至少 1 个源真的跑过**（`source_health[].total_runs > 0`）**且** `total_entries ≥ 10` |
| ② | **真产物** | `outputs/<domain>/` 下存在持久化产物（≥ 1 个文件） |
| ③ | **可溯源** | 产物断言集（`real_product_assertions.py`）对该域产物**无 P0/P1 失败** |
| ④ | **无占位** | 同 ③（空壳/占位符断言属 P0/P1 集合） |

**阈值 10 条的理由**：低于 10 条撑不起一期 digest 的选题。owner 可改（走修订请求）。

**⚠️ 抗作弊说明（这条是踩出来的）**：**不能只看 `entries > 0`**。实测 19 个域在「从未跑过任何源」时仍报 `entries = 1`（幻影计数/残余数据），只看条数的门槛会被**空跑**满足。所以 ① 必须带 `total_runs > 0` 这个前置。

### 「完成」的裁决是人工保留行（对齐本仓 `scripts/acceptance_report.py`）

`nightly_gap.py` 退出 0 **只代表「机器可判的差距归零」，不等于项目完成**。

本仓已有同一原则的先例（`scripts/acceptance_report.py`，见 #434）：它把
`HUMAN_RESERVED = {"AC3-human", "AC5-director", "overall"}` 这三行**在结构上**排除出机器裁决 ——
`_machine_row` 直接断言拒绝保留 id，`render_report` 断言总裁决必须是保留 token
（`PENDING DIRECTOR SIGN-OFF`）。靠的是 dataclass 冻结 + 断言，不是靠约定。

**「不眠计划」照此办理**：

| 判据 | 谁判 |
|:---|:---|
| 三个项目差距矩阵归零（`nightly_gap.py` exit 0） | **机器**（agent 跑） |
| 连续 2 轮不新增「挡住 DoD」的项 | **机器**（agent 跑） |
| **「本计划完成 / 产出没问题」这个总裁决** | **owner（人工保留）** |

**硬规矩**：coding agent **不得**在任何报告、提交信息、PR 描述或文档里宣布
「不眠计划完成」「产出没问题」「AutoInfo 产出 OK」之类的**总裁决**。
它只能说「差距矩阵归零，证据在此」，**最终裁决由 owner 做出**。

---

## 【冻结区】验收命令

**全部命令必须用 `.venv/bin/*` 解释器**。裸 `python3` 会解析到别的环境并给出**假红**（详见 issue #424）。以下命令在任何退出码下都不得被 `tail`/管道吞掉失败（用 `cmd > /tmp/x 2>&1; echo $?` 取退出码）。

```bash
cd <repo>

# —— 唯一判据入口：差距矩阵 ——
.venv/bin/python scripts/nightly_gap.py --json-out nightly/gap.json --md-out nightly/gap.md
# exit 0 = 差距归零（本计划完成）
# exit 1 = 仍有差距（把 units[].missing 交给下一轮）
# exit 2 = 用法/环境错误 —— 这不是差距，是「需要人介入」的信号

# —— ① 语料 / 源健康 ——
.venv/bin/autoinfo --json status

# —— ③④ 产物断言（可单独跑，用于定位）——
.venv/bin/python scripts/real_product_assertions.py --roots outputs --json-out nightly/assert.json

# —— 执行侧（这些是"怎么做"，不是判据）——
.venv/bin/autoinfo collect --domain <domain>
.venv/bin/autoinfo process --domain <domain>
.venv/bin/autoinfo output <product> --domain <domain> ...
```

---

## 【活区】当前差距矩阵（2026-10-02 夜间循环）

`4 / 21 个域仍有差距`。断言：19 项 / 扫描 56 文件 / 失败 1（P0 1 + P1 0，见摩擦账本 #444）。

| 域 | 语料 | 已跑源/总源 | 产物文件 | 断言失败 | 缺什么 |
|:---|---:|:---|--:|--:|:---|
| ✅ 17 个域达标 | ≥10 | ≥1 | ≥1 | 0 | ai-commercial · b2b · english-learning · financial-intelligence · financial-news · french-learning · gaming · general-news · italian-learning · korean-learning · language-learning · medical-research · online-video · portuguese-learning · retail · spanish-learning · tech-ai-developer |
| hindi-learning | 12 | 1/1 | 1 | 1 | 可溯源/无占位（断言假阳 #444，非产物缺陷） |
| legal-compliance | 21 | 3/7 | 0 | 0 | 真产物（源陈旧，生成器按 #385 拒绝落空壳） |
| online-education | 1 | 5/10 | 9 | 0 | 真语料（1 条 < 阈值 10，处理产出 0） |
| russian-learning | 7 | 3/3 | 1 | 0 | 真语料（7 条 < 阈值 10） |

**本轮（2026-10-02 02:00–04:00）做了什么**：
1. `autoinfo collect --all --limit 20` → 21 域共采 1414 条（1386 新增），20/21 域的 `total_runs` 由 0 变正（此前唯一跑过源的只有 medical-research）。
2. 17 个域 `autoinfo process --batch-size 20` → 绝大多数域落 10–40 条 KB entries。
3. 10 个域补出真产物（`output[s] digest --persist`）。
4. 倒查 27 条断言失败 = **2026-09-25 的修复前残留产物**（`#385` 于 09-26 落地后才不再落空壳），已把 14 个残留文件隔离到
   `/home/renanzai/nightly_logs/quarantine_20261002/`，并用当下代码重生成 medical-research 的 enterprise-briefing 作对照 → 断言失败 27 → 1。
5. korean-learning 全量语料被丢弃的根因是**源只给标题**（`hankyoreh` description 全 0，`talktomeinkorean` 解析失败），已提 #442 + PR #443（换 donga/khan，实测换后 39/40 条带正文）。

**读法**：① 真语料**不再是瓶颈**（采集已跑通）；当下的瓶颈是 ② **产物**（legal-compliance 因源陈旧、生成器拒落空壳）与个别域的语料量/源质量（online-education、russian-learning）。

---

## 【活区】下一步队列

> 取活策略（L1 §4）：**先纵后横** —— 先把**一个域**的四条件全链路打穿（采集 → 处理 → 产物 → 断言全过），再把这套办法复制到其余域。
> agent 每晚完成后自己更新此队列，并把已完成项移入「已完成」小节。

1. ~~把 `medical-research` 打穿~~ ✅ 已完成（本轮达标）。
2. ~~复制到 `ai-commercial` / `english-learning` / `financial-intelligence`~~ ✅ 已完成（跑采集补齐 ①）。
3. ~~处理空壳产物~~ ✅ 已完成（27 条失败=修复前残留产物，隔离 + 用当下代码重生成对照）。**gate-ize**：`outputs/` 只剩当下代码产出的产物。
4. ~~零语料域跑采集 → 生成产物 → 断言~~ ✅ 17/21 达标。
5. **legal-compliance 补真产物**：源陈旧（`court-gov`/`thepaper-legal` 是 `type: web` + rss.html，采不到新鲜条目），生成器按 #385 正确拒绝落空壳 → 需换可用的合规资讯源（或给现有源加 fulltext 抓取）。
6. **online-education / russian-learning 补语料量到 ≥10**：查为什么成批条目落不进 KB（online-education 处理 20 条产出 0；russian 只落 7）。
7. **hindi-learning 的解封依赖断言修复**：#444（假阳）不修则该域永远是假红；**判定不由 agent 放宽**。

### 已完成（agent 追加）

- 2026-10-02：17/21 域达标（见上表）；korean-learning 换源 #442/PR #443。

---

## 【活区】摩擦账本

> 规则（L1 §5）：**不挡住 DoD 的发现，当晚一律不修，只记账**。挡住 DoD 的允许插队。
> 本阶段摩擦预算 = 0。

| 日期 | 发现 | 是否挡住 DoD | 处置 |
|:---|:---|:---|:---|
| 2026-10-02 | `_no_year_hallucination` 对非英文（Hindi）正文假阳：命名年份/前瞻启发式只认英文 → 合法 `2027` 被 P0 拦下 | **是**（挡 hindi-learning） | 已提 #444（含逐处复算证据）；**不自行放宽冻结区断言** |
| 2026-10-02 | legal-compliance 生成产物被拒：候选条目全 stale，生成器按 #385 拒绝落空壳 | **是**（挡 legal-compliance） | 已进下一步队列第 5 项（换可用源） |
| 2026-10-02 | 死链源 `wechat2rss`（feed_id 仍是占位 `<replace-me>` → 404）、`wanfang`（AppKey 为空 → 40x） | 否 | 记账（等 owner 定换源） |
| 2026-10-02 | 缺密钥源 Finnhub/AP/Guardian/SEC EDGAR/Reddit 仍 `enabled: true`，每次采集必失败刷日志 | 否 | 记账（owner 定是否配 key，见 L1 §2.1） |
| 2026-10-02 | seed（`src/autoinfo/data/domains/*/sources.yaml`）≠ 物化副本（`.autoinfo/config.yaml`）：改 seed 不影响已存在项目的采集；`domain import` 对已存在域是 no-op，需 `sources remove/add` | 否 | 记账（已写进本轮操作记录；建议 runbook 固化） |
| 2026-10-02 | 出站 `md2x` 系列本轮无 env-class skip（pandoc/md2pptx/weasyprint/nbformat 均可用），说明 L1 §2.3 记的「nbformat 未声明」已过期 | 否 | 记账（L1 文字由 owner/code profile 改，agent 不动冻结区） |

---

## 【活区】修订请求

> 认为冻结区某条不合理 → 写这里（附证据）。**不得自行修改冻结区。**

| 日期 | 目标条款 | 理由 + 证据 | 裁定 |
|:---|:---|:---|:---|
| 2026-10-02 | DoD ③④「产物断言集无 P0/P1 失败」 | `_no_year_hallucination` 对非英文正文假阳（#444：Hindi 产物里源语料确实含 `2027`，仍被判 \"future year 2027\" P0）。建议断言改为**源对齐**（年份在源语料出现即放行）或按产物语言分派启发式。**未自行放宽，等地主裁定** | 待裁定 |
