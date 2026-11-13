# journey-collect-raw — 指挥者：采集入库（Raw 唯一入口）

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：至少一个域配置了可用源
- **步骤（仅终态断言）**：collect 产出条目，全部经 01-Raw 入口（来源元数据齐全）
- **期望终态**：终态：Raw 条目存在且 source_url/source_type/source_platform 完整
- **挂接场景ID**：collection
- **证据类型**：命令输出 + Raw 条目路径
