<!--
结构示意 · 待编译 · 未装 gh-aw CLI · 不得直接执行（D3 降级，Owner 决策 7）
依据：02 稿 §4.4 + A6；gh-aw 为 Public Preview（R-1），语法快速漂移——逐键以官方
Frontmatter Reference 当前版为准；落地前必须 `gh aw compile --strict` 校验并生成 .lock.yml，
校验失败即停止该动作。本文件在安装 gh-aw 并编译前不会被 GitHub Actions 执行（.md 非工作流格式）。
-->
---
on:
  pull_request:
    types: [opened, synchronize]
permissions: read-all                # 只读 by default
engine: copilot
safe-outputs:
  add-comment:                       # 唯一写入出口：固定 JSON 裁决
    max: 1
---
你是 Tester。先读 AGENTS.md → .agents/roles/tester.md → .agents/expectations/INDEX.md。
按 .agents/expectations/checkpoints.md 评估终态、逐 checkpoint 出 verdict，
以角色契约的固定 JSON 评论；严禁改任何文件/期望。
