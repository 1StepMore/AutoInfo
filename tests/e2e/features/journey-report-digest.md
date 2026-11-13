# journey-report-digest — 终端用户：周报/简报产出

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：域内有条目（无 LLM key 时走确定性合成，provenance 如实记录）
- **步骤（仅终态断言）**：digest/report 产物落盘、结构完整（D1/D2 门禁不 block）
- **期望终态**：终态：产物路径存在且非空，格式断言通过
- **挂接场景ID**：output-digest-report
- **证据类型**：产物路径 + 产物文件
