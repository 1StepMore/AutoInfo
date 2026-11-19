# 文本侧 66 格验证判定（2026-11-19）

> Owner 2026-11-19 显式授权：文本侧矩阵由 code 侧 agent 在本机验证（覆盖
> `docs/dev/matrix-ownership.md` 的默认归属）。判定口径：`docs/dev/matrix-verdict-policy.md`。

## 证据要素

- **commit sha**：`3eaf38a4`（main @ release 1.33.2）
- **key 状态**：`keyed`（`AUTOINFO_LLM_API_KEY` 环境变量；config `api_key` 为空串）
- **模型**：spark-x2.6（openai 兼容端点，config `llm.*`，未改）
- **时间**：2026-11-18 17:42–18:41 UTC（本地 11-19 01:42–02:41）
- **spec**：`docs/dev/specs/end-user-matrix.yaml`（22 个已实现文本 pair × 3 域 = 66 格）
- **逐格 reached 与错误类**：`matrix.json`（81 行，含音视频 15 行历史 assert 行，未动）
- **命令**：见下「三轮运行」；报告生成器把完整命令写进 `matrix.md` 头部

## 四轮运行（只重跑红格，无整批重刷）

| # | 时间 (UTC) | 范围 | 触发原因 |
|:--|:--|:--|:--|
| 1 | 17:42–17:57 | 22 pair × 3 域 = 66 格，`--force` 全量真生成 | 仓内 matrix 是 10-27 `--only-assert` 旧行 |
| 2 | 18:01–18:33 | 12 gated pair × 3 域 = 36 格，`--force` | 修复 `detect_llm_available` 漂移后重跑被误判格 |
| 3 | 18:34–18:41 | 19 格（checkpoint 置 pending） | 口径「每格最多 2 次尝试」：对 quality/抖动类红格给第 2 次 |
| 4 | 18:58–19:45 | 33 格（checkpoint 置 pending） | 语料刷新后按口径只重跑红格：两域 collect+process（ai-commercial +104、medical-research +40 条 KB entries） |

- Run 1 命令：`capability_matrix.py --domains ai-commercial,language-learning,medical-research --only <22 个文本 pair> --force --out docs/dev/validation-reports/capability-27x3`
- Run 2 命令：同上，`--only` 换为 12 个 gated pair（column:markdown、enterprise-briefing:html/markdown、magazine-digest:html/markdown、premium-briefing:html/markdown、presentation:agent/html/markdown、tutorial:agent/markdown）
- Run 3 命令：13 个涉及 pair 的 `--only` + `--checkpoint <临时>`（19 格置 pending，其余格保持已判定被跳过；绿格未动）
- Run 4 命令：Run 3 的 checkpoint 机制，20 个涉及 pair、33 格置 pending；绿格未动

## 最终判定（66 格，Run 4 后）

**总格数 66 / 绿（L3）66 / 红 0 / skip 0 / flaky 1（1.5%，<10% 阈值）**

| 域 | L3 |
|:--|:--|
| ai-commercial | **22/22** |
| language-learning | **22/22** |
| medical-research | **22/22** |

Run 3 后的红格（quality 18 + deterministic 15，全部在 ai-commercial / medical-research）
在语料刷新后（Run 4）**一次性全部转为 L3 真生成**——印证红格根因是数据侧（语料过期/过薄），
非代码或模型能力问题。Run 1–3 的分轮红格定性保留在 git 历史与本节下方存档。

## 最终判定（66 格）

**总格数 66 / 绿（L3）33 / 红 33 / skip 0 / flaky 1（1.5%，<10% 阈值）**

| 域 | L3 | 红格构成 |
|:--|:--|:--|
| language-learning | **22/22** | 0 |
| medical-research | 9/22 | L1 9、empty 4 |
| ai-commercial | 2/22 | L1 9、empty 9、stale 2 |

### 红格三档定性（Run 3 后存档；Run 4 语料刷新后已全部转绿）

- **quality（18）**：`L1`——产物存在但 L2 结构断言失败（`l2=fail(body_text/links/headings/body_words)`）。
  根因一致：**输入语料太薄**（如 ai-commercial 仅 3 条、medical 3-6 条输入），LLM/确定性回退填不出满足结构
  断言的正文/链接/标题。已给第 2 次尝试（run 3），18 格中 17 格复现、1 格转绿（见 flaky）。
- **deterministic（15）**：13 格 `blocked-empty-artifact`（`is_no_data_product=True`，无足够输入，重试无意义，
  不烧尝试）+ 2 格 `blocked-stale-sources`（`StaleSourceError: All 4 candidate entries … are stale`，
  错误信息明示需 re-collect）。
- **transient（0）**：无超时/429 类失败。run 2 曾有 1 格 `blocked-generation-error`
  （`ValueError: slides=0`，模型输出抖动），run 3 第 2 次尝试产出产物（记 L1，quality 类）。

### flaky（pass(retry)）记录

- `language-learning/tutorial:agent`：run 2 首跑 `L2-degraded`（LLM 输出不可用 → KB 回退
  `tutorial_llm_unusable`，判红）；run 3 第 2 次尝试 **L3 真生成**（28KB tutorial-markdown-…-182350）。
  首跑失败证据：run 2 stdout（`Tutorial LLM output unusable for domain 'language-learning'`）。
- flaky 比例 1/66 ≈ **1.5%**，远低于 10% 停刷线；未调低任何断言。

## 根因与修复

1. **`detect_llm_available` 漂移（已修，代码改动）**：36 格 gated 曾被误判 `blocked-no-llm-key`。该检测器只信
   `load_config().llm.api_key`（本仓 config 为空串、key 走环境变量），而真实调用路径
   `resolve_primary_api_key`（`src/autoinfo/config.py`，单一事实源）有环境变量兜底。修复：检测器对齐
   `resolve_primary_api_key`（`scripts/coverage_matrix.py`，capability/coverage/validation_delivery 三个调用方
   同时受益）；测试对齐 + 新增 env 兜底用例（`tests/validation/test_coverage_matrix.py`，60 passed，ruff clean）。
   **待 owner 决定是否走 PR。**
2. **数据侧红格（已解决）**：ai-commercial 与 medical-research 的采集语料过期/过薄。owner 2026-11-19
   授权自主推进后，对两域执行 `collect` + `process`（ai-commercial 108 items → +104 KB entries；
   medical-research 41 items → +40 KB entries；1 条因标题含冒号在 Windows 建目录失败，记独立跟进项），
   随后按口径只重跑 33 个红格 → **全部 L3**。`language-learning` 语料新鲜、首轮即 22/22 全绿，是对照证明。

## 边界说明

- 音视频 15 格未重跑（code 侧分工另案）；`matrix.json` 中对应 15 行仍是 10-27 assert 旧值，**不代表本次判定**。
- 运行期产生的 `outputs/capability-matrix/`（约 60+ 件产物 + provenance）为 runtime 状态，未提交。
- medical-research 生成期间存在两条无关告警：2 个历史 02-Draft 文件缺失（promotion failed）、
  language filter `en` 空集回退（issue #53 既有行为），不影响本判定。
