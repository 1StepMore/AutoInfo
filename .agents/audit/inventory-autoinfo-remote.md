# Inventory — AutoInfo @ 333a11c2  SOURCE=REMOTE（见 02 稿 §7.5）

> 取证方式：gh api 只读调用（rulesets / contents / pr list）+ `git remote -v`。与 LOCAL 报告互斥、不混用；本报告**不含任何本地推断**。

## 远端仓库事实

| 项 | 值 | 取证 |
|---|---|---|
| origin | `git@github.com:1StepMore/AutoInfo.git`（SSH）/ 1StepMore/AutoInfo | git remote -v |
| 可见性 / 默认分支 | PUBLIC / main | gh repo view |
| 附加远端 | `backup` / `backup-https` → renanzai40/AutoInfo_BackUp（**不在任务单范围，R5 禁止推送**） | git remote -v |
| open PR | 无（0 个 open PR，含 draft） | gh pr list --state open |
| 经典分支保护 | 无（API 404 "Branch not protected"）——治理全部走 rulesets | gh api branches/main/protection |

## Rulesets（③层仓库治理）

| 项 | 值 |
|---|---|
| ruleset | `main-protection`，enforcement=**active**，target=branch |
| 规则类型 | pull_request / required_status_checks / deletion（禁删）/ non_fast_forward（禁强推） |
| PR 规则 | required_approving_review_count=**0**；dismiss_stale_reviews_on_push=true；require_code_owner_review=false |
| 必过 checks（10 项，strict_required_status_checks_policy=**true**） | Conventional Commits title · DCO · Doc drift guard · Fast subset coverage on changed modules · Lint · Mypy (changed files) · Release scope · Scenario portability · Test suite (fast subset) · Derived doc/surface parity |
| bypass actors | **无**（无人可绕过） |

## 远端 main 上的 workflows（8 份）

ci.yml · coverage.yml · guard.yml · nightly.yml · pr-title-check.yml · preview-smoke.yml · release-please.yml · release-pr-auto-merge.yml

## CODEOWNERS（远端 main 生效）

`* @1StepMore` + 细分：/src/autoinfo/mcp/ · /src/autoinfo/output/ · /docs/ · /.github/ 全部 @1StepMore。注意 ruleset `require_code_owner_review=false` —— CODEOWNERS 仅产生 review 请求，**不构成强制门**。

## 与方针 ③层的差距（仅记录，处置在 P3）

1. **无路径级 push rules**（如保护 `.agents/expectations/`）——方针 ③层可选能力，本轮不新增远端设置（预授权未含改远端治理配置，改设须 Owner）；以"期望文件改动只能经 PR + ruleset 十项必过"作为等效约束，登记于 §8.4。
2. required checks 已含 `Derived doc/surface parity` —— A13 的新增 gate 若要升级为**必过**须改 ruleset（Owner 远端操作），本轮仅做到 CI 内强制（guard.yml/ci.yml 失败即红），升级登记为 Owner 待办。
