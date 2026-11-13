# journey-system-health — 指挥者：系统健康巡检

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：仓库检出完整，`autoinfo` CLI 可用
- **步骤（仅终态断言）**：status --json 域清单可见；doctor --json 结构化健康数据返回
- **期望终态**：终态：status 与 doctor 都 success，且输出含域与健康字段
- **挂接场景ID**：cli-core, observability
- **证据类型**：命令输出（JSON envelope）
