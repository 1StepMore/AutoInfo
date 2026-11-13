# journey-agent-discovery — Agent：工具发现链

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：MCP server 可进程内调用
- **步骤（仅终态断言）**：health_check→tools/list→list_domains→schemas 全链可达
- **期望终态**：终态：发现场景步骤全 pass（envelope 结构合规）
- **挂接场景ID**：discovery, output-discovery
- **证据类型**：MCP envelope 输出
