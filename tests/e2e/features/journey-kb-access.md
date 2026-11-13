# journey-kb-access — 终端用户：知识库查询

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：Wiki 中有已晋升条目
- **步骤（仅终态断言）**：search_knowledge_base/filter_custom_fields 可查询
- **期望终态**：终态：查询返回结构化结果
- **挂接场景ID**：kb-access
- **证据类型**：MCP envelope 输出
