# journey-agent-multiturn — Agent：多轮上下文与回调

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：MCP server 可进程内调用
- **步骤（仅终态断言）**：tool 选择、多轮上下文保持、回调注册/移除可用
- **期望终态**：终态：三个 agent 交互场景全 pass
- **挂接场景ID**：agent-tool-selection, agent-multiturn-context, agent-callbacks
- **证据类型**：MCP envelope 输出
