# journey-collect-recovery — 指挥者：采集失败恢复

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：可注入失败的源配置（场景内自备）
- **步骤（仅终态断言）**：失败被记录，恢复路径可用（不丢已采集条目）
- **期望终态**：终态：失败场景 status=failed 被如实上报，恢复步骤通过
- **挂接场景ID**：collect-failure-recovery
- **证据类型**：命令输出（失败注入报告）
