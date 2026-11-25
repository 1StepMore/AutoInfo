---
# 结构示意 · 待编译（D3 降级解除记录，Owner 决策 7 / A6 / R-1）：本文件由
# gh-aw 编译生成 .lock.yml 后生效；语法以官方 Frontmatter Reference 当前版为准，
# 落地必须 gh aw compile --strict 校验。.md 源不直接作为工作流执行。
on:
  pull_request:
    types: [opened, synchronize]
permissions:                        # 只读 + Copilot 推理额度（组织计费，无需 PAT）
  contents: read
  copilot-requests: write            # engine: copilot 的官方免 PAT 路径
  issues: read
  pull-requests: read
engine: copilot
safe-outputs:
  add-comment:                       # 唯一写入出口：固定 JSON 裁决
    max: 1
---
你是 Tester。先读 AGENTS.md → .agents/roles/tester.md → .agents/expectations/INDEX.md。
按 .agents/expectations/checkpoints.md 评估终态、逐 checkpoint 出 verdict，
以角色契约的固定 JSON 评论；严禁改任何文件/期望。
