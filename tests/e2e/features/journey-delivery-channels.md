# journey-delivery-channels — 终端用户：交付通道配置

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：产品已安装（渠道未配置的按引擎口径 unconfigured）
- **步骤（仅终态断言）**：email/rest 等通道配置可读回、状态可查
- **期望终态**：终态：交付通道场景步骤 pass 或 unconfigured(带原因)
- **挂接场景ID**：delivery-channels
- **证据类型**：命令输出 + 配置读回
