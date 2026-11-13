# journey-enduser-lifecycle — B1 付费客户旅程：订阅→交付→改配置

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：产品已安装（支付通道未配置按引擎口径 unconfigured）
- **步骤（仅终态断言）**：enduser 生命周期（订阅/交付/偏好）端到端可达
- **期望终态**：终态：生命周期场景步骤 pass 或 unconfigured(带原因)
- **挂接场景ID**：enduser-lifecycle, enduser-preferences
- **证据类型**：场景 per-step 结果 + envelope
