# journey-kb-lifecycle — 知识库全生命周期（tier 归置）

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：产品已安装
- **步骤（仅终态断言）**：Raw→Draft→Wiki 各层读写路径可达，01-Raw 唯一入口不变量成立
- **期望终态**：终态：生命周期场景步骤全 pass
- **挂接场景ID**：kb-lifecycle
- **证据类型**：场景 per-step 结果
