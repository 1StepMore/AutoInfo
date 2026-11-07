# Scope — src/autoinfo/

此地何为真（scope 层，只描述地点，不写角色）：

- 本目录是**唯一行为事实源**：产品全部行为由这里的代码定义；runtime 产物漂移一律修源码，不手改产物。
- 入口三层：`mcp/`（MCP-first 主入口，`server.py` = hub，`_TOOL_DISPATCH` 单表派发）·
  `cli/`（MCP 镜像，1:1 参数）· `api/`（FastAPI :8741，canonical 8/8 由 surface_parity 对账）。
- 加采集源 = `collectors/` 一个类 + `registry.py` 一次注册；不改派发链。
- LLM 判定模型 config-first（`llm.judgment_model` → `llm.model`），不写死模型常量。
- Prompts 是 `$name` 占位符（非 `{name}`），文本被 `tests/test_prompts.py` 字节级钉住。
- 改动本目录 → 必须有对应测试（tests/ 镜像本目录结构）。
