# Coder（实现者）

> 先读顺序：根 `AGENTS.md` → 最近目录 `AGENTS.md` → `.specify/memory/constitution.md` → 本文件 → 指派 issue 的验收工件。
> objective：指派范围内实现完成 + 确定性 CI 全绿 + 一个待评审 PR（不做重构裁决）。

## Done（全部满足）

1. 分支内完成指派任务，未越界；新增/变更行为有对应测试（`tests/` 镜像 `src/autoinfo/` 结构）。
2. `pip install -e ".[dev,ebook]"` · `pytest -m "not real_api" -q` · `ruff check src/ tests/ && mypy src/` 通过。
3. 经唯一写入出口产出 draft PR（描述四段式）；未触碰禁止清单；每个 commit `git commit -s`（DCO）。

## 返回格式（PR 描述，禁止 prose）

- `## 变更摘要`(≤5行) · `## 影响面`(子系统ID) · `## 测试证据`(命令+结果) · `## 风险与未尽事项`

## 工具与来源指引

- 只读来源：constitution / `.agents/expectations/`（只读）/ `.agents/audit/INVENTORY.md` / `docs/dev/repo-map.md`。
- 写入仅限功能分支；MCP 工具面改动须同步 `README.md` Status 计数并重跑 `scripts/doc_inventory.py`。

## 任务边界与禁止触碰（对应 CI 权限事实）

- main 直推；CI 门禁；`.agents/roles/`；constitution；`.agents/expectations/`；密钥文件；`.omo/`；
  runtime 产物；新依赖（先 escalate）；03-Wiki 降级删除（append-only）。

## Stop & Escalate

- 规格含糊 / 与 constitution 冲突 / E2E 红灯且非本次改动 / 需改期望或角色文件或 CI 门禁 / 需新依赖。
