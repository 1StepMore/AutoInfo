# journey-domain-setup — 指挥者：配置新域与源

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：产品已安装，Agent 侧可调 MCP 工具
- **步骤（仅终态断言）**：add_domain/add_source 配置落盘；domain list 可见新域
- **期望终态**：终态：域配置可读回，源配置完整
- **挂接场景ID**：domain-management
- **证据类型**：命令输出 + 配置文件路径
