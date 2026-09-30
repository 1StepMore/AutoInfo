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

## 【活区】当前差距矩阵（基线 2026-09-30）

`21 / 21 个域仍有差距`。断言：19 项 / 扫描 59 文件 / 失败 27（P0 2 + P1 25）。

| 域 | 语料 | 已跑源/总源 | 产物文件 | 断言失败 | 缺什么 |
|:---|---:|:---|--:|--:|:---|
| medical-research | 96 | 4/7 | 24 | 2 | 可溯源/无占位 |
| ai-commercial | 50 | 0/4 | 13 | 0 | 真语料 |
| english-learning | 44 | 0/2 | 4 | 0 | 真语料 |
| financial-intelligence | 208 | 0/11 | 11 | 0 | 真语料 |
| general-news | 1 | 0/24 | 14 | 8 | 真语料 + 可溯源/无占位 |
| gaming | 1 | 0/10 | 4 | 8 | 真语料 + 可溯源/无占位 |
| legal-compliance | 1 | 0/7 | 4 | 0 | 真语料 |
| online-education | 1 | 0/10 | 9 | 0 | 真语料 |
| online-video | 1 | 0/11 | 2 | 0 | 真语料 |
| tech-ai-developer | 1 | 0/17 | 4 | 0 | 真语料 |
| financial-news · language-learning | 1 | 0/10 · 0/3 | 2 · 2 | 0 | 真语料 |
| b2b · retail | 1 | 0/8 · 0/6 | 0 | 0 | 真语料 + 真产物 |
| french · hindi · italian · korean · portuguese · russian · spanish-learning | 0 | 0/各 | 0 | 0 | 真语料 + 真产物 |

**读法**：真语料是**全局瓶颈**（20/21 域没有任何源跑过）；产物层只有 13 个域有文件，其中 gaming/general-news 的产物是空壳（断言 8 条失败）；medical-research 是唯一有真实采集链的域，但产物仍有 2 条 P0/P1 断言失败。

---

## 【活区】下一步队列

> 取活策略（L1 §4）：**先纵后横** —— 先把**一个域**的四条件全链路打穿（采集 → 处理 → 产物 → 断言全过），再把这套办法复制到其余域。
> agent 每晚完成后自己更新此队列，并把已完成项移入「已完成」小节。

1. **把 `medical-research` 打穿**：它已有真实采集链（4/7 源跑过、96 条），只差 2 条产物断言失败 → 修到 `nightly_gap.py` 对该域返回 ✅。这是**验证整条路径可行的最短路径**。
2. 复制到 `ai-commercial` / `english-learning` / `financial-intelligence`（已有 44–208 条语料与产物，只差"源真跑过"）→ 跑采集补齐 ①。
3. 处理空壳产物：`gaming` / `general-news` 的 8 条断言失败（`_column_deep_dive` / `_report_sections`：缺 Deep Dive 段、无 Sections 元数据 = 空壳）。
4. 零语料域（french / hindi / italian / korean / portuguese / russian / spanish-learning）：跑采集 → 生成产物 → 断言。

### 已完成（agent 追加）

---

## 【活区】摩擦账本

> 规则（L1 §5）：**不挡住 DoD 的发现，当晚一律不修，只记账**。挡住 DoD 的允许插队。
> 本阶段摩擦预算 = 0。

| 日期 | 发现 | 是否挡住 DoD | 处置 |
|:---|:---|:---|:---|

---

## 【活区】修订请求

> 认为冻结区某条不合理 → 写这里（附证据）。**不得自行修改冻结区。**

| 日期 | 目标条款 | 理由 + 证据 | 裁定 |
|:---|:---|:---|:---|
