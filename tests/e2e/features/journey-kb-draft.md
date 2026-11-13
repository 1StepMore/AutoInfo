# journey-kb-draft — Agent：Raw→Draft 草稿创建

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：域内有 Raw 条目
- **步骤（仅终态断言）**：create_kb_draft 仅能从 Raw 创建（外部创建被拒）
- **期望终态**：终态：Draft 创建成功且来源可追溯
- **挂接场景ID**：kb-draft
- **证据类型**：MCP envelope 输出
