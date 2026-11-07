<!--
结构示意 · 待编译 · 未装 gh-aw CLI · 不得直接执行（D3 降级，Owner 决策 7）
依据：02 稿 §4.4 + A6（M1：draft 依据挂 gh-aw create-pull-request.draft 默认 policy，
不挂 GitHub 博客）；R-1 逐键以官方当前版为准，落地前必须 `gh aw compile --strict`。
-->
---
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
