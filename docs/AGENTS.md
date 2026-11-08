# Scope — docs/

此地何为真（scope 层，只描述地点，不写角色）：

- `docs/dev/` 是开发行为事实源：specs/ 为抽取规格，adr/ 一文件一决策（不可变），plans/ 为整改计划。
- 计数类事实的唯一来源是 `README.md` → Status 表（`scripts/doc_inventory.py --check` 强制）；
  本目录任何文档不得自携计数。
- `docs/archive/`、`docs/dev/archive/` 是历史快照（guard.yml 白名单），禁止改写历史结论。
- `docs/user/` 是用户旅程文档（黑盒验收的旅程来源）；`docs/dev/DEBT.md` 是技术债台账。
- 写文档先查 `.agents/audit/INVENTORY.md`（AUTO-GENERATED 文档地图），改完重跑生成器。
