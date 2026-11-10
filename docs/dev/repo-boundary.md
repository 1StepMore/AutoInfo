# 跨仓边界 — AutoInfo 只负责 AutoInfo

> Loaded on demand from `AGENTS.md` §0.6 (#745). 这是硬边界，不是建议。
> 参照 `e2e-test-suite` `AGENTS.md` §0.2 的已验证做法：那里同样用 5 行挡住跨仓执行。

`AutoMedia`、`Omni` 三模块（`Omni_Pre_Processor` / `Omni_Localizer` / `Omni_Re_Formatter`）与
`e2e-test-suite` 是**别的产品线**，不是本仓的模块、夹具或依赖。硬约束：

- **不改那些仓**：不编辑、不开分支、不提交、不在其工作树里 `git checkout/fetch/merge/push`
- **不在那些仓开 PR / issue**；它们的 issue / PR / backlog 永远不是本仓作业项 —— **即使本仓文件提到它们**
- 不因本仓脚本调用其 CLI 就"顺手修"；在那边的缺陷 → **在本仓开 issue 点名归属仓 + 证据**
  （file:line、命令、输出），到此为止
- 本仓文档里出现的别仓名字/编号（含 `docs/dev/plans/NIGHTLY.md` 的跨仓立案号、
  `NIGHTLY-PLAN-L1.md` 的其它项目章节）一律是**跨仓事实引用，不是作业项**

## 为什么需要这一条

同一个"万能维护提示词"发到两侧，套件侧靠同样的 5 行做到了「天天读 L1、读跨仓立案号，但一次没跨过去」；
本仓此前没有任何边界条款，于是"文档里提到的别仓问题"被读成"本仓的作业项"，真的去改了对方仓。
这是可复用的已验证做法，不是新设计。

## 与 §0 其它条款的关系

§0.1-§0.4 管安全（密钥、API key、03-Wiki、期望工件），§0.5 管优先级，§0.6 管范围。
范围越界不产生数据损坏，但会产生跨仓的、无人 review 的副作用 —— 因此与安全条款同列，而不是放进
下游的 MUST NOT 表。
