# journey-video-output — 终端用户：视频产出（环境受限如实上报）

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：完整 Chrome/bun/ffmpeg 才可真渲染；缺任一按引擎口径 unconfigured
- **步骤（仅终态断言）**：视频产物或 blocked 读数（不假 FAILED）
- **期望终态**：终态：场景步骤 pass 或 unconfigured(带原因)
- **挂接场景ID**：output-video
- **证据类型**：场景 per-step 结果
