# Harness 运行事实速查

> 本文件是 AutoInfo 的**运行事实真身**：解释器落位、必需环境变量、缺件症状、门禁顺序、已知坑。
> 通用执行规则（边界 / 权限分级 / 合并判定）不在本仓，由 Owner 侧维护。
> `AGENTS.md` 是 pointer-only，只指向本文件，不复制正文。

## 解释器与安装

| 项 | 内容 |
|:--|:--|
| Linux / WSL | `.venv/bin/python`（`.venv` 在 `.gitignore` 里） |
| Windows 原生 | `.venv\Scripts\python.exe` |
| 安装（运行） | `make install` |
| 安装（开发） | `make dev-install`（含测试与 lint 依赖） |
| 已装包校验 | `<py> -c "import autoinfo; print(autoinfo.__version__)"` |

## 必需环境变量

| 变量 | 用途 | 缺了会怎样 |
|:--|:--|:--|
| `AUTOINFO_LLM_API_KEY` | 主模型 key；写进 `.autoinfo/config.yaml` 时必须是 `api_key: ${AUTOINFO_LLM_API_KEY}`，**不要写明文** | `autoinfo doctor` 报 `❌ LLM: no API key configured` |
| （可选）fallback 各端点 key | 跨端点 fallback 必须携带**自己的** `${ENV}` 引用，绝不继承 primary key | 该端点降级为不可用，doctor 的 `fallback chain` 计数变少 |

**`.env` 约定**：本仓**不读任何 `.env` 文件**（写了无效），只认进程环境变量。要证明"真的没 key"，必须用干净进程环境跑，否则会被别处的 `.env` 骗过。

`${VAR}` 引用未设置时，加载期会给出 `config reference "${VAR}" resolved to empty (#792)` 警告 —— 这是**警告不是失败**，doctor 会按红/黄/绿给判定。

## 门禁顺序（DoD）

```
make lint        # ruff check src/ tests/ + mypy src/
make test        # 全量；单文件测试用 <py> -m pytest -q <path>
make doc-check   # 只在改了 docs/ 或任何文档时追加
```

**`make doc-check` ≠ CI doc 门**：PR 的 `Derived doc/surface parity`（guard.yml `derived-facts` job）跑**四段**——`doc_inventory --check`、`surface_parity --check`、`coverage_matrix --check-enduser-doc`、`autoinfo.gov check`；`make doc-check` 只含 gov check + coverage-matrix + demo-domains，**不含 doc_inventory**。改任何 docs/ 文件必须：`make doc-check` + `python3 scripts/doc_inventory.py`（再生成 `docs/dev/doc-inventory.md` 与 `.agents/audit/INVENTORY.md`）+ `python3 scripts/surface_parity.py --check`。这是本仓最常见的假绿——实测踩过：只跑 make doc-check 三段本地全绿，CI 仍红在 doc_inventory stale。

## 已知坑

1. **Windows CI ≠ 全量等价**：`windows-smoke` job（#803/#804）只覆盖安装 + ruff + `mypy --platform linux` + E2E baseline + 小型 Windows 敏感子集；Chrome/ffmpeg/外网依赖与全量 ~3000 测试不上该 runner——别把"CI 绿"读成"Windows 全量可用"。
2. **`make lint` 含 mypy**：`mypy src/` 是硬门，类型标注缺失会直接红，不是警告。
3. **产物判据不放宽**：`outputs/<domain>/` 为空就是未达标，不许拿 `outputs-archive/` 的旧产物凑数。
4. **`${ENV}` 未设 ≠ 空串静默**：新版本会给加载期警告 + doctor 分级，看到警告先查环境，不要急着改代码。
5. **治理入口唯一**：`python -m autoinfo.gov` 是唯一治理入口；`AGENTS.md` 行数有硬上限（C3，≤200 行），加内容要按"下移进 `docs/dev/`"的方式做。
6. **Windows 原生 `mypy src/` 会误报 3 条**：`src/autoinfo/mcp/validation.py:650` 的 POSIX-only 属性（`os.killpg/getpgid/SIGKILL`）在 Windows stubs 下不存在（该行有 `os.name == "nt"` 运行时守卫，运行时安全）。本地 Windows 等价命令：`mypy --platform linux src/`——与 ubuntu mypy job 和 `windows-smoke` job 同一类型契约（ci.yml 有注释）。别为消掉它改产品代码。

## 队列

```
gh issue list -l agent-ready --state open
```
