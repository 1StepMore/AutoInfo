# journey-kb-promote — Agent：Draft→Wiki 晋升（生产步骤）

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：有可晋升 Draft
- **步骤（仅终态断言）**：promote_kb_draft 走 CurationGate；03-Wiki append-only
- **期望终态**：终态：晋升成功；降级/删除类操作被拒绝
- **挂接场景ID**：kb-promote
- **证据类型**：MCP envelope 输出
