# journey-process-extraction — 指挥者：process 抽取（质量门禁）

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：域内有已采集条目；LLM 配置可解析（无 key 时按引擎口径 unconfigured）
- **步骤（仅终态断言）**：process 走 G0-G3/G7 门禁，产出 01-Raw 结构化条目
- **期望终态**：终态：process envelope success 或 unconfigured(带原因)
- **挂接场景ID**：processing, kb-extraction
- **证据类型**：命令输出 + 门禁读数
