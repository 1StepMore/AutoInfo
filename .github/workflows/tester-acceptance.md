---
# 结构示意 · 待编译（D3 降级解除记录，Owner 决策 7 / A6 / R-1）：本文件由
# gh-aw 编译生成 .lock.yml 后生效；语法以官方 Frontmatter Reference 当前版为准，
# 落地必须 gh aw compile --strict 校验。.md 源不直接作为工作流执行。
on:
  pull_request:
    types: [opened, synchronize]
permissions: read-all              # 只读；推理凭据走 COPILOT_GITHUB_TOKEN（见 #917 评论）

engine:
  id: copilot
  model: gpt-4.1        # 显式模型名：'auto' 别名依赖 catalog 解析，无 Copilot 授权时解析失败
safe-outputs:
  add-comment:                       # 唯一写入出口：固定 JSON 裁决
    max: 1
---
你是 Tester。先读 AGENTS.md → .agents/roles/tester.md → .agents/expectations/INDEX.md。
按 .agents/expectations/checkpoints.md 评估终态、逐 checkpoint 出 verdict，
以角色契约的固定 JSON 评论；严禁改任何文件/期望。
