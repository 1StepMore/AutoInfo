# journey-output-formats — 终端用户：column/tutorial/presentation/ebook 产出

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：域内有条目
- **步骤（仅终态断言）**：四类产物模板渲染完整（空 section 不留孤儿标题）
- **期望终态**：终态：各产物落盘且模板断言通过
- **挂接场景ID**：output-column, output-tutorial-presentation, output-ebook
- **证据类型**：产物路径 + 场景 per-step 结果
