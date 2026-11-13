# tests/e2e/features/ — E2E 期望的执行层

> 期望的**执行**，非定义（定义唯一事实源 = `.agents/expectations/`，方针 §5.1）。
> E2E 选型 Owner 已拍板（决策 8）：**不引入 Playwright 等新框架**，旅程逐条挂既有验证场景 ID。
>
> - **E2E_RUNNER** = 既有验证场景引擎 `autoinfo.mcp.validation.run_scenario`（`run_validation_scenario` MCP 工具同一引擎）
> - **E2E_CMD** = `pytest tests/e2e/test_e2e_features.py -q`
>
> 基线：首批 20 条旅程（#729，agent 代选、Owner 可调整）。GAP-01（无可执行 E2E 基线）已解除。

## 格式约定（对齐 `.agents/expectations/checkpoints.md`）

每个旅程一个文件：`journey-<旅程名>.md`，五个字段 = `前置 / 步骤(仅终态断言) / 期望终态 / 挂接场景ID / 证据类型`。
`挂接场景ID` 行是**机器可读挂接**：harness 解析该行的逗号分隔场景 ID，逐个跑真实引擎。

## 执行语义（harness = `tests/e2e/test_e2e_features.py`）

- 挂接场景全部 `passed` → 旅程绿；
- 场景报引擎的 `unconfigured`（环境前提缺失，带 `unconfigured_reason`）→ 旅程 **SKIPPED**，reason 以
  `blocked-unconfigured:` 开头——诚实 blocked 读数，不是 FAILED，也不是静默通过；
- 其余（`failed` / 场景 ID 不存在 / 旅程文件缺字段）→ 红。
- 另有三条契约测试：旅程基线数量（≥20）、五字段完整、挂接 ID 全部存在于场景库（场景改名在这里红，
  而不是无声缩水基线）。

## 首批 20 条旅程（#729 基线；agent 代选，Owner 可增删）

| 旅程 | 覆盖 | 挂接场景 |
|---|---|---|
| journey-system-health | B3 指挥者健康巡检 | cli-core, observability |
| journey-domain-setup | 域与源配置 | domain-management |
| journey-collect-raw | 采集入库（Raw 唯一入口） | collection |
| journey-collect-monitor | 采集监控 | collection-monitor |
| journey-collect-recovery | 采集失败恢复 | collect-failure-recovery |
| journey-collector-coverage | 采集器真实链路 | collectors-e2e |
| journey-process-extraction | process 抽取+门禁（需 key） | processing, kb-extraction |
| journey-kb-draft | Raw→Draft | kb-draft |
| journey-kb-promote | Draft→Wiki 晋升（需 key：G4 无条件） | kb-promote |
| journey-kb-access | 知识库查询 | kb-access |
| journey-kb-lifecycle | 知识库生命周期 | kb-lifecycle |
| journey-report-digest | 周报/简报产出（需 key） | output-digest-report |
| journey-output-formats | column/tutorial/presentation/ebook | output-column, output-tutorial-presentation, output-ebook |
| journey-video-output | 视频产出（环境受限如实上报） | output-video |
| journey-delivery-channels | 交付通道 | delivery-channels |
| journey-delivery-schedule | 定时调度 | delivery-schedules, cron-schedules |
| journey-enduser-lifecycle | B1 订阅→交付→改配置 | enduser-lifecycle, enduser-preferences |
| journey-agent-discovery | Agent 工具发现 | discovery, output-discovery |
| journey-agent-multiturn | Agent 多轮上下文与回调 | agent-tool-selection, agent-multiturn-context, agent-callbacks |
| journey-privacy-export | 隐私与数据导出 | privacy-gdpr-export, kb-import-export |

## Windows 可移植注记（2026-11-14 基线校准时发现并修复）

场景库的种子/校验步骤原为 POSIX 专属形态（`python - <<'PY'` heredoc 与多行 `python -c '<体>'`）。
cmd.exe 无 heredoc、其 C runtime 按换行切 argv，多行体在 Windows 上必死于 shell/python 层。
`_run_cli_step` 的 Windows seam（`_materialize_python_body`，#729）现把这两种形态物化为临时 `.py`
再执行，POSIX 路径不变；`_cmd_quote_compat` 继续负责单行命令的引号翻译。

## 已知边界

- 挂接场景的环境前提（`requires_env`）缺失时旅程读数为 blocked-unconfigured——这是引擎的诚实读数，
  不是基线失败；keyed 全绿要等 `AUTOINFO_LLM_API_KEY` 可解析的部署。
- `kb-promote` 场景的静态 entry_id 期望（slug 形态）与现行 KBStore 日期+哈希 id 派生不匹配（有 key 也
  会红）——已知陈旧缺陷，待引擎支持步骤间 id 链接或场景改写后解除（见 #729 PR 记录）。
