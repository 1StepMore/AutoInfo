# journey-delivery-schedule — 指挥者：定时调度

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：产品已安装
- **步骤（仅终态断言）**：cron/delivery_schedules 配置可读回且调度状态可查
- **期望终态**：终态：调度场景步骤 pass
- **挂接场景ID**：delivery-schedules, cron-schedules
- **证据类型**：命令输出 + 配置读回
