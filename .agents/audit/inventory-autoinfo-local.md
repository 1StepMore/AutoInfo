# Inventory — AutoInfo @ 333a11c2  SOURCE=LOCAL（见 02 稿 §7.5）

> 基线 commit：`333a11c22d73e1361dd6f74a143f9375c785e5be`（2026-11-07，v1.28.2）。取证方式：本地工作树（git status/log/ls-files、文件系统只读扫描）。与 REMOTE 报告互斥、不混用。

| ID | 子系统 | 路径 | 类别 | 测试现状 | 文档现状 | CI 覆盖 | 判定依据 | 处置建议(A编号) |
|----|--------|------|------|----------|----------|---------|----------|----------------|
| S-01 | MCP 服务器面 | src/autoinfo/mcp/（208 文件） | 源码 | tests/mcp/ 镜像覆盖；149→151 工具由 doc_inventory 双向核对 | docs/dev/specs/mcp-tools.md + README Status 表 | ci.yml（test fast subset）+ guard.yml（doc_inventory 工具表对账） | 仓库自述 MCP-first 入口；repo-map 详注 | A10（目录级 AGENTS.md） |
| S-02 | CLI | src/autoinfo/cli/（35 文件，31 命令组） | 源码 | tests/cli/ | AGENTS.md Quick Start + repo-map | ci.yml（test） | MCP 的 CLI 镜像，1:1 参数 | A10 |
| S-03 | REST API | src/autoinfo/api/（16 文件，FastAPI :8741） | 源码 | tests/api/ | docs/dev/cli-mcp-rest-parity.md | guard.yml（surface_parity --check 对账 8/8 canonical） | surface parity 已进 CI | — |
| S-04 | Collectors | src/autoinfo/collectors/（34 文件，30 handler + registry） | 源码 | tests/collectors/（+cassettes/） | repo-map 列全 30 源 | ci.yml（test） | Collector ABC 契约 + registry 派发 | A10 |
| S-05 | Output 生成 | src/autoinfo/output/（28 文件，digest/report/tutorial/presentation/export/video/ebook…） | 源码 | tests/output/ | repo-map 详注 | ci.yml（test） | 8 产物模板在 S-06 | A10 |
| S-06 | 域配置/模板/Prompts | src/autoinfo/data/（52 文件：domains/*/sources.yaml + 11 .j2 + prompts/ 16 文件） | 源码（配置资产） | tests/test_prompts.py 字节级钉住 | docs/dev/new-domain-guide.md | ci.yml（test）+ guard.yml（gen_demo_domains_table --check） | prompts.py $name 占位符单源 | A10 |
| S-07 | 质量门禁层 | src/autoinfo/{quality,qa,grounding,self_claims,translation_qa,terminology,dedup,quality_constraints}.py | 源码 | tests/quality/ + tests/qa/ + tests/process/ | docs/dev/specs/quality-gates.md | ci.yml（test） | G0–G7/D1–D3 代码实现 | — |
| S-08 | KB 管线 | src/autoinfo/{kb,promotion,importer}.py | 源码 | tests/kb/ | AGENTS.md Architecture Rules + docs/adr/0001/0002 | ci.yml（test） | 01-Raw→Draft→Wiki 代码强制（CurationGate/WIKI_PROTECTED） | — |
| S-09 | 管线编排 | src/autoinfo/{collect,process,pipeline}.py | 源码 | tests/{collectors,process,integration}/ | docs/dev/specs/pipeline.md | ci.yml（test） | 两阶段收集/处理 | — |
| S-10 | LLM 引擎与配置 | src/autoinfo/{llm,config,defaults}.py | 源码 | tests/{llm,config}/ | docs/dev/llm-config.md | ci.yml（test） | 判定模型 config-first（#195） | — |
| S-11 | Gov 治理模块 | src/autoinfo/gov/（19 文件） | 源码 | tests/gov/（近期最活跃测试区，19 commit） | docs/dev/validation-governance.md + .github/governance-contract.toml | guard.yml（gov contract check + gov check + derived_parity） | ADR-0014 单一治理入口 | — |
| S-12 | Delivery | src/autoinfo/delivery/（13 文件） | 源码 | tests/delivery/ | docs/dev/specs/delivery.md | ci.yml（test） | 频率门禁/门禁报告 | — |
| S-13 | 平台服务散点 | src/autoinfo/{alerts,billing,cost,email_sender,embeddings,cefr,recommend,metrics,audit,doctor,status,user_store,notifications,checkpoint,consumption,logging,db,models,schema,section_parser,textutil,urlnorm,keywords,urlnorm…}.py（约 30 个单文件） | 源码 | 各有对应 tests/ 子目录或单测（tests/{alerts,billing,cost,email,monitor}/ 等） | 散点 docstring 为主 | ci.yml（test） | 10-30 审计已标注部分名实不符项（🔶#7/#8/#9） | — |
| S-14 | 测试套件 | tests/（451 文件，~7000 用例） | 测试 | — | tests/TRIAGE.md | ci.yml（fast subset）+ coverage.yml + nightly.yml | E2E 缺位（无 tests/e2e） | A9/A14 |
| S-15 | 确定性仪器 | scripts/（53 文件：doc_inventory/surface_parity/coverage_matrix/ax_metrics/quality_gate/agent_review/battery…） | 源码（工具） | tests/scripts/ | 各脚本 docstring + docs/dev/agent-infrastructure-audit-2026-10-30.md | guard.yml（4 件已进 CI）；battery/ax_metrics 零接线（🟡） | 10-30 审计 #10/#11/#17/#19 判级 | A13（增量接线） |
| S-16 | 文档 | docs/（148+5 文件）+ 根 README/CHANGELOG/AUTHORS/CONTRIBUTING/GOVERNANCE/SECURITY/CODE_OF_CONDUCT | 文档 | — | guard.yml Drift Guard 禁字符串 + doc_inventory living-docs 对账 | guard.yml | dev/ 与 adr/ 是行为事实源；archive/ 为历史快照（白名单） | A1/A10 |
| S-17 | CI/治理配置 | .github/（16 文件：8 workflows + CODEOWNERS + governance-contract.toml + templates + dependabot + fixtures） | CI | tests/{gov,validation}/ 钉住 workflow 行为（test_nightly_workflow/test_release_workflow） | AGENTS.md Merging a PR 节 | —（自身即 CI） | ruleset 十项必过（见 REMOTE 报告） | A7/A13 |
| S-18 | OpenCode Agent Skills | .opencode/skills/（8 文件：6 个 SKILL.md 对） | 文档（agent 程序性知识） | — | 自身即指令 | — | 官方 Agent Skills 格式；与方针 .agents/skills/ 精神等价 → **原位保留不迁移**（防双源），由根 AGENTS.md 指针引用 | D4 适配 |
| S-19 | 根 meta | AGENTS.md（200 行整）/ Makefile / pyproject.toml / Dockerfile / docker-compose.yml / release-please-config.json | CI/文档混合 | — | AGENTS.md 自身是 agent 入口 | Makefile 为本地入口 | AGENTS.md 恰好触顶 200 行（C3 零余量） | A1/A9 |
| S-20 | 运行时产物 | collections/ knowledge/ outputs/ logs/ autoinfo.db backups/ build/ validation-runs/ validation-deliveries/ exports/ reports/ deliverables/ demo-packages/ pkg-AutoInfo.zip knowledge_graph_export.json | （未跟踪，不入库） | — | — | — | .gitignore 覆盖；**不适用 A11**（无跟踪文件可标头注），清理留 Owner 裁决 | —（疑似待废弃，Owner 裁决） |

## 待废弃清单（仅标记不删除；三条件证据）

**跟踪文件中：0 条满足三条件**（无引用 ∧ 无 CI 覆盖 ∧ 文档声明废弃）。docs/archive/ 与 docs/dev/archive/ 是**有意保留的历史快照**（guard.yml 白名单注明理由），不构成待废弃。

**疑似待废弃（未跟踪运行区产物，不适用 A11 头注机制，留 Owner 裁决清理）**：
| 路径 | 证据 |
|---|---|
| pkg-AutoInfo.zip / pkg-AutoInfo/ | 顶层打包残留，未跟踪，无 CI/文档引用 |
| knowledge_graph_export.json（根） | 导出产物落在根目录，未跟踪 |
| backups/ reports/ deliverables/ demo-packages/ exports/ | 运行/交付产物目录，未跟踪，repo-map 未登记 |

## 敏感文件清单（仅路径，不展开内容）

- 无真实凭据文件命中：无 `.env*`、`*.pem`、`*.key`、`*credential*` 文件。
- `tests/cli/test_source_credential_alerts.py` — 测试代码（凭据告警功能的测试），非凭据。
- `docs/dev/required-api-keys.md` — 环境变量名目录文档（AGENTS.md 指针引用），无 key 值。
- `.autoinfo/gov/dod7-nokey.json` — 运行时治理快照（文件名含 "nokey"），未读内容。
- git 历史抽样命中均为知识库文章标题含 "secret*" 的误报（knowledge/ 下未跟踪域产物）。
- 建议 Owner 合并前跑一次 GitHub secret scanning（§8.4 清单项）。

## 现有 agent 设施清单（保留/合并/适配 → D4）

| 设施 | 路径 | 内容摘要 | 处置 |
|---|---|---|---|
| 根 AGENTS.md | AGENTS.md（200 行） | 指针式索引：架构规则/MUST NOT/合并规则/工具发现/LLM 配置 | **D4 合并**：重构进 A1 新模板（保留全部有效条目，路由表+tiebreaker+§0 安全为新增），diff 交 Owner |
| OpenCode Skills | .opencode/skills/（6 个 SKILL.md） | deep-modules/doc-manager/maintainer-workflow/validation-runner（开发方）+ autoinfo-skill/translator-qa-skill（运营方） | **保留原位**（官方 Agent Skills 格式；不迁移到 .agents/skills/ 防双源），根 AGENTS.md 挂指针 |
| MCP 客户端配置 | .cursor/mcp.json、.opencode/mcp.json、.claude/claude_desktop_config.json | 三套开箱 MCP 接入 | **保留**（产品接入面，与本次整改正交） |
| 验收框架 | docs/dev/acceptance-framework.md（AC1–AC9） | 二元判据 + 证据目录 | **适配**：.agents/expectations/INDEX.md 指针索引挂 AC1–AC9（决策 5） |
| 验证场景引擎 | src/autoinfo 内 validation 相关 + tests/validation/ | 182 场景三态判定 | **保留**；E2E 骨架旅程挂其场景 ID（决策 8） |
| 工作流章程 | docs/dev/workflow-charter.md + 七阶段方法论 | 开发流程 canonical | **保留**（constitution 抽取时作出处之一） |
| 治理契约 | .github/governance-contract.toml + src/autoinfo/gov/ | ADR-0014 机器可读治理 | **保留**（③层已有事实，与方针 ruleset 层互补） |
| 编排工作区 | .omo/（gitignored） | Sisyphus 式计划/证据 | **不碰**（AGENTS.md 明令） |
| 不存在项 | — | 无 .claude/agents/、.github/agents/、.specify/、copilot-instructions.md、CLAUDE.md、目录级 AGENTS.md | A3/A4/A5/A10 净新增 |

## 前置缺口登记（A14 / R-5）

| 缺口ID | 类型 | 证据 | 影响的验收项 | 状态 |
|---|---|---|---|---|
| GAP-01 | 无E2E基线 | 全仓无 tests/e2e/；CI 无 E2E job；182 验证场景为产品验证而非仓库 E2E 基线 | P4-S4 E2E 校准；A9 骨架挂载 | PENDING-前置（E2E 选型已拍板=映射场景，但可执行基线仍缺） |
| GAP-02 | 仪器接线缺口 | ax_metrics.py CI/Makefile 零接线（10-30 审计 #19 🔶）；L1 battery 零接线（#11 🟡） | A13 增量接线范围 | PENDING-前置（决策 B 数据源断流，属 10-30 计划范围，本轮不动） |

## 回填参数区

```
BUILD_CMD=pip install -e ".[dev,ebook]"     # ci.yml test job 实际安装命令
TEST_CMD=pytest -m "not real_api" -q        # ci.yml "Test suite (fast subset)" 逐字
LINT_CMD=ruff check src/ tests/ && mypy src/  # Makefile lint 目标逐字（本机 make 缺失→直接命令执行）
E2E_CMD=pytest tests/e2e/test_e2e_features.py -q   # #729 基线落地（2026-11-14），GAP-01 解除
E2E_RUNNER=autoinfo.mcp.validation.run_scenario    # 决策 8：既有验证场景引擎，20 旅程挂场景 ID
REPO=AutoInfo（origin=git@github.com:1StepMore/AutoInfo.git）
```

## 本地取证备注

- AGENTS.md 恰 200 行（C3 上限零余量）→ A1 必须置换瘦身。
- 最近 20 commit 活跃区：src/autoinfo(56)、docs/dev(54)、tests/gov(19)、.opencode/skills(11)、.github/workflows(7) —— 仓库处于高频双写状态（AGENTS.md 自述"two agents write here"），角色契约价值高。
- .opencode/node_modules 存在于工作区但**未被跟踪**（git ls-files 仅 8 个 skills 文件）——运行产物，不处置。
