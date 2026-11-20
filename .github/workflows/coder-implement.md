---
# 结构示意 · 待编译（D3 降级解除记录，Owner 决策 7 / A6 / R-1）：本文件由
# gh-aw 编译生成 .lock.yml 后生效；语法以官方 Frontmatter Reference 当前版为准，
# 落地必须 gh aw compile --strict 校验。
# M1：draft 依据挂 create-pull-request.draft 默认 policy，不挂 GitHub 博客。
on:
  issues:
    types: [labeled]
permissions: read-all
engine: copilot
safe-outputs:
  create-pull-request:               # 唯一写入出口；draft 为默认 policy、不可运行时覆盖
    title-prefix: "[coder] "
    draft: true
---
你是 Coder。读 AGENTS.md → .agents/roles/coder.md；在功能分支实现，
产出待评审 draft PR（四段式描述）；严禁触碰 .agents/expectations/ 与 .agents/roles/。
