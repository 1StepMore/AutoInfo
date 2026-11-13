# journey-collect-monitor — 指挥者：采集运行监控

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：已有采集历史
- **步骤（仅终态断言）**：采集状态/健康可查询
- **期望终态**：终态：监控输出含采集统计，无未处理异常
- **挂接场景ID**：collection-monitor
- **证据类型**：命令输出
