# tests/e2e/features/ — E2E 期望的执行层（骨架）

> 期望的**执行**，非定义（定义唯一事实源 = `.agents/expectations/`，方针 §5.1）。
> E2E 选型 Owner 已拍板（决策 8）：**不引入 Playwright 等新框架**，旅程逐条挂既有验证场景 ID；
> `E2E_CMD` / `E2E_RUNNER` = UNKNOWN（可执行基线缺失，inventory GAP-01，PENDING-前置）。

## 格式约定（对齐 `.agents/expectations/checkpoints.md`）

每个场景文件一个旅程：`<旅程名>.md`，字段 = `前置 / 步骤(仅终态断言) / 期望终态 / 挂接场景ID / 证据类型`。

## 示例占位（首个旅程，待 Owner 确认后补全为可执行）

<!-- 示例：journey-collect-digest.md
前置：medical-research 域已配置至少 1 个可用源
步骤：仅终态断言——collect 产出 Raw 条目 → process 过门禁 → digest 产物存在
期望终态：.agents/expectations/INDEX.md @EXP-SCEN 所挂场景全部 pass
挂接场景ID：<从 tests/validation/ 场景清单取证，待 Owner 指定>
证据类型：命令输出 + 产物路径
-->

## 前置缺口

- GAP-01：无可执行 E2E 基线（E2E_CMD/E2E_RUNNER=UNKNOWN）→ P4-S4 校准标 `PENDING-前置`，不得静默跳过。
