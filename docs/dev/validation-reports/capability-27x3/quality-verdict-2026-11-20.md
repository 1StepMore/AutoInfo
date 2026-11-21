# 质量判定（capability matrix 27×3，2026-11-20）

> Owner 目标（2026-11-20 直接指令）：矩阵覆盖率 100%，且每个格子产出的东西质量合格。
> 质量结论必须来自真模型；fake 只准用于链路/契约/覆盖，记 confidence=mock。
> 三条判据同时满足才算达成，判据命令 `scripts/goal_matrix_quality.py`（goals.md P2 goal-cmd）。

## 证据要素

- **commit sha**：`e92a8b8f`（main @ #885 合并后）；本判定文档与证据随 PR 入库后以此为准
- **真模型**：spark-x2.6（openai 兼容端点，`.autoinfo/config.yaml llm.*`，未改）；key 走
  `AUTOINFO_LLM_API_KEY` 环境变量（BYOK，config `api_key` 为空串）；本会话全程 keyed，零 fake/mock 判定
- **时间**：2026-11-19 17:42 UTC – 11-20 01:3x UTC（本地 11-20 凌晨班）
- **命令**：矩阵驱动器 `scripts/capability_matrix.py`；L0 `scripts/quality_gate.py`；
  L1 `scripts/agent_review/battery.py --semantic`；判据命令 `scripts/goal_matrix_quality.py`
- **口径**：`docs/dev/matrix-verdict-policy.md`（跨仓契约，未改）；本判据在驱动器之上更严
  （诚实 block 不算达成；LLM 供料格式必须 keyed）

## 判据 1：矩阵满格且 0 missing —— 满足

- 81/81 格全部 L3（驱动器行级 `reached=L3`，无 pending、无 missing；0 红 0 skip）。
- keyed 纪律：80/81 keyed；1 格 unkeyed（language-learning/report:video，code 侧 11-19 跑，
  媒体格式按结构验收，本判据容忍并在下方声明——修复需 code 侧 keyed 重跑，见交接）。
- 矩阵产物 `matrix.json`/`matrix.md` 的 A/V 15 行来自 code 侧 11-19 12:26 run（#881 入库），
  文本 66 行来自 11-18/19 keyed 真生成；ai-commercial/tutorial:markdown 在本轮约束性重生一次
  （tutorial-markdown-20261119-180800-192971.md，L3 真生成）。

## 判据 2：质量门全绿 —— 满足

**L0（确定性结构门，三域 capability-matrix 产物目录）**：exit 0，无缺陷。
本轮 L0 首跑抓出并处置 5 个缺陷：

| 缺陷 | 定性 | 处置 |
|---|---|---|
| 4× premium-briefing-markdown F1 空壳 | 淘汰残留（run 1–3 失败中间产物，无现行行引用） | 删除，逐件 sha256 留痕（logs/artifact-residue-cleanup-2026-11-20.md） |
| 1× ai-commercial/tutorial:markdown H2 截断 | 门规则误报（枚举值 `student` vs 散文 `students`） | 修复门（PR #885 已合并），约束性重生该格 → L3 |

**L1（agent battery，真模型）**：三域全部 PASS：

| 域 | verdicts | 结果 |
|---|---|---|
| ai-commercial | 2 | 2 PASS |
| language-learning | 2 | 2 PASS（**首跑 1 FLAG → 规则澄清后复跑全 PASS，全程见下**）|
| medical-research | 1 | 1 PASS |

## L1 FLAG 全程（诚实留痕）

1. **首跑（2026-11-20 ~02:05）**：language-learning 1 FLAG `local-market-presence`：
   "entries are drawn exclusively from English-language sources with no Chinese AI news or
   target-language local-market material reaching any entry … absence class #190 confirmed"。
2. **复核**：language-learning 是**英语教学域**（topics：English Vocabulary / Reading
   Comprehension / 中英文 Listening & Pronunciation），目标语素材（英语）在条目中已存在；
   规则原文把 "Chinese AI news / target-language material" 捆绑且未说何者何时适用 → LLM 误套中文分支。
3. **误治与回滚（本会话内闭环）**：按误读给该域加中文市场源（sspai）并重跑 26 格；
   中途复核发现方向错误（中文数码内容对英语教学域是污染不是补缺），中止 run，
   完整回滚：源配置移除、6 条 trial KB 条目清除（逐条 sha256 留痕）、28 个孤儿产物删除
   （logs/artifact-residue-cleanup-2026-11-20.md / logs/kb-purge-2026-11-20.md）。
   被杀的 run 未写入任何 matrix 行（驱动器收尾才写 JSON），矩阵行从未被污染。
4. **规则澄清**：`blindspots.yaml` `local-market-presence` 按域受众澄清期望语言
   （zh 市场域要中文 AI 新闻；教学域要其所教语言的素材，不得要求域不教的语言）。
   PR #888。检查不删不减：每个双语域照常跑，目标内容全缺席仍 FLAG。
5. **复跑**：澄清后真模型复跑 language-learning battery → **2/2 PASS**（note 引用澄清后口径）。

## 判据 3：证据已入库 —— 满足（随本 PR）

- 判据命令 `scripts/goal_matrix_quality.py`（goals.md P2 goal-cmd）机检六项（矩阵满格/L3/keyed/
  L0/L1/证据 git 跟踪），比驱动器退出码更严。
- 证据文件：matrix.json/md、evidence-pack.md（重投影）、本判定文档、三域 battery JSON、
  cleanup/purge 日志——全部 git 跟踪，交由判据命令验证 `git ls-files` 可见性。
- 本轮**零 fake/mock 判定**：所有质量结论出自 spark-x2.6 真模型；fake 仅允许链路/契约/覆盖
  测试（repo 测试套件既有约定），真判定记录不含 confidence=mock 标记。

## 口径与边界

- 本判据（goal-cmd）比驱动器更严：驱动器 exit 0 允许诚实 block；本判据要求 81/81 全 L3。
- unkeyed 媒体行容忍声明：language-learning/report:video（unkeyed，code 侧 11-19 跑，媒体格式
  结构验收）。更严处置（keyed 重跑）需 code 侧机器（本机缺 bun），已写进交接。
- KB 索引 parity 深度失衡（~1300 无行文件 + 27 对同 ID 异容双文件 + wiki 后门草稿）是**仓卫生债**，
  不在本目标三条判据内；已开 issue #887 带执行契约，wiki 后门草稿删除需 owner 显式指令（§0）。
- Mimosa deep scan（hook 要求，2026-11-19T18:01Z）：**inconclusive**（部分覆盖），
  99 条静态发现（数条 HIGH：eval @ quality.py:3362、命令注入类于归档脚本与 mcp/validation.py）——
  未宣称安全；建议专项复核，不属本判定范围。

## 交接（handoff）事项

1. code 侧（有 bun 的机器）keyed 重跑 language-learning/report:video，替换 unkeyed 行（变严方向）。
2. issue #887（KB parity 深度失衡 + wiki 后门草稿 owner 裁决）。
3. Mimosa inconclusive 99 findings 专项复核（安全侧，非本目标）。
4. 本机 PATH 修复建议：pytest 前置 `.venv/机器 Scripts`（harness-run-facts #9 同款），
   否则 CLI help 测试误红（已在 #887 记录）。
5. `goals.md` P2 注册（PR #889 待并入）与 goal-cmd 机检口径见 PR #889 的脚本 docstring。
