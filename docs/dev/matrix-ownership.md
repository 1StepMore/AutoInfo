# 矩阵归属（模态分工）

> owner 2026-11-19 定：**视频 / 语音 / 图片 = code profile（本机 code 侧）**；**文本 = owner 侧 agent / harness**。
> 判定口径见 `docs/dev/matrix-verdict-policy.md`（跨仓契约，勿只改本仓副本）。

## 谁跑哪些格

本仓 capability 矩阵 = **81 格**（3 domain × 27 已实现 product:format）。

| 模态 | 格（product:format）| 格数 | Owner | 跑法 |
|:--|:--|--:|:--|:--|
| 语音 | `digest:audio` `report:audio` | 6 | **code** | `--only digest:audio --only report:audio` |
| 有声书 | `digest:audiobook` `report:audiobook` | 6 | **code** | `--only digest:audiobook --only report:audiobook` |
| 视频 | `report:video` | 3 | **code** | `--only report:video` |
| 文本 | markdown 24 / html 18 / agent 12 / json 6 / epub 6 | **66** | **owner 侧** | 同上，按 format 逐类 `--only` |

命令模板（本机）：

```bash
.venv/bin/python scripts/capability_matrix.py \
  --domains ai-commercial,language-learning,medical-research \
  --only report:video --force \
  --out docs/dev/validation-reports/capability-27x3
```

报告落点：`docs/dev/validation-reports/capability-27x3/`（`matrix.json` + `matrix.md`）。
覆盖矩阵（`scripts/coverage_matrix.py`）与全矩阵执行器（`src/autoinfo/validation_matrix.py`）同样按此分工念：**音视频格＝code，文本格＝owner 侧**。

## 现状（文本侧 2026-11-19 本机重验；音视频 2026-11-14 本机跑，未提交）

- 文本 **L3 达标 66/66 全绿**（三域各 22/22，全部 keyed 真生成）。路径：修 `detect_llm_available`
  key 解析漂移 → 两域重采（ai-commercial +104、medical-research +40 条 KB entries）→ 按口径只重跑红格。
  判定与四轮证据：`docs/dev/validation-reports/capability-27x3/text-66-verdict-2026-11-19.md`。
  flaky 1/66（1.5% < 10% 停刷线）。
- 音视频（11-14 旧值，未重跑）：L3 10/15，3 格生成报错、2 格源过期——仍待 code 侧重跑。
  `matrix.json` 里对应 15 行是 10-27 assert 旧行，不代表本次判定。

## 硬规矩

- 提交矩阵产物前必须**先重跑**；不许手改数字。
- 仓里提交的 `matrix.md` 是 2026-10-28 的（#642），**已滞后于代码**，以重跑为准。
