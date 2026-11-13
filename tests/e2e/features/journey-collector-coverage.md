# journey-collector-coverage — 采集器端到端（真实 handler 链路）

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：仓库检出完整；不要求外网（handler 按场景契约执行）
- **步骤（仅终态断言）**：采集器注册表驱动：加源=一个类+一次注册的契约可执行
- **期望终态**：终态：场景全部步骤 pass
- **挂接场景ID**：collectors-e2e
- **证据类型**：场景 per-step 结果
