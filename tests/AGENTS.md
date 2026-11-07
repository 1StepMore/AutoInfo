# Scope — tests/

此地何为真（scope 层，只描述地点，不写角色）：

- 本目录镜像 `src/autoinfo/` 结构；新增/变更行为必须有对应测试（单元/集成归实现者）。
- CI 跑 fast subset：`pytest -m "not real_api" -q`；标记 `real_api` 的用例只在 nightly/手动跑。
- `tests/validation/` 是验证场景引擎的单测；场景本体在 `src/autoinfo` 侧，182 场景三态判定。
- `TRIAGE.md` 是身份锁（不得替测试改名逃避 triage）。
- `tests/e2e/features/` 是 E2E 期望的**执行**（非定义）；期望定义唯一事实源在 `.agents/expectations/`。
