# Expectations Index — 期望唯一事实源入口

> 本 INDEX 是期望层的**唯一入口**（指针索引，不复本内容——Owner 决策 5）。
> 期望的定义事实源 = 既有验收体系；本文件只做挂接与版本锚。改期望 = 仅 Owner 显式指令（根 AGENTS.md §0-4）。
> Tester 按 `checkpoints.md` 评估终态；验证优先级：确定性规则 > 视觉反馈 > LLM judge。

| id | 标题 | 来源（定义事实源） | owner | 版本 |
|---|---|---|---|---|
| EXP-AC | 验收框架 AC1–AC9（二元判据 + 证据目录） | `docs/dev/acceptance-framework.md` | Owner | @333a11c2 |
| EXP-AR | 架构不变量（KB 管线/质量门禁/MUST NOT） | 根 `AGENTS.md` Architecture Rules + MUST NOT | Owner | @333a11c2 |
| EXP-GATES | 质量门禁目录与激活语义（G0–G7/D1–D3） | `docs/dev/specs/quality-gates.md` | Owner | @333a11c2 |
| EXP-SCEN | 验证场景体系（182 场景三态判定） | `tests/validation/` + 场景引擎 | Owner | @333a11c2 |
| EXP-DEMO | Demo 发布标准（DoD + 残差登记） | `docs/demo-release-standard.md` + `docs/known-limitations/demo-quality-residuals.md` | Owner | @333a11c2 |
| EXP-E2E | E2E 旅程基线（执行层 = `tests/e2e/features/`；E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`，E2E_RUNNER = 验证场景引擎 `autoinfo.mcp.validation.run_scenario`；首批 20 旅程，#729） | `tests/e2e/features/README.md` | Owner | v1-baseline-20 (2026-11-14) |

> 版本锚约定：`@<commit>` 指当前基线；期望内容变更时（仅 Owner）须更新对应行版本并记 ADR。

## scenarios/

（空——指针索引模式下，新增独立验收场景才在 `scenarios/<ID>.md` 落地；C7 校验 INDEX↔scenarios 一一对应、无孤儿。）
