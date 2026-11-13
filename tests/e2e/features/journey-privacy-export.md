# journey-privacy-export — 终端用户：隐私与数据导出

> 执行层挂接（E2E_RUNNER = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`；
> E2E_CMD = `pytest tests/e2e/test_e2e_features.py -q`）。决策 8：不引入新框架，旅程逐条挂场景 ID。

- **前置**：产品已安装
- **步骤（仅终态断言）**：GDPR 导出/软删除恢复/KB 导入导出可用
- **期望终态**：终态：隐私与导出场景步骤 pass
- **挂接场景ID**：privacy-gdpr-export, kb-import-export
- **证据类型**：场景 per-step 结果 + 导出产物路径
