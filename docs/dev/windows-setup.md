# Windows 原生上手指南

> `AGENTS.md` §Windows 原生、README Quick Start 与 CONTRIBUTING Getting started 的 Windows
> 注记都指向本文件（issue #980）。Linux/macOS 用户不需要它；CI 两侧门禁差异见
> `harness-run-facts.md`「已知坑」。

## 解释器与 venv

| 项 | Windows 原生 | Linux/macOS 对照 |
|:--|:--|:--|
| venv 解释器 | `.venv\Scripts\python.exe` | `.venv/bin/python` |
| 建 venv | `py -m venv .venv`（或 `python -m venv .venv`） | `python3 -m venv .venv` |
| 激活（PowerShell） | `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| 激活（CMD） | `.venv\Scripts\activate.bat` | — |
| 不激活直接用 | `.\.venv\Scripts\python.exe -m pytest -q` | `.venv/bin/python -m pytest` |

- Windows 默认**没有 `python3` 命令**（只有 `python` 与 `py` 启动器）——本仓文档里的 `python3`
  一律读作 `python`。
- PowerShell 首次激活若报「禁止运行脚本」：
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`。
- venv 激活也补不出 `python3.exe`（Scripts 里只有 `python.exe`）——所以裸 `make` 在 Windows 会
  解析到系统解释器并报 `ModuleNotFoundError: autoinfo`（见下节与 `harness-run-facts.md` 坑 7）。

## make 等价命令

GNU make 不是 Windows 自带件；Makefile 只是 POSIX 薄别名层（见 Makefile 头注释），每个别名下的
真实命令都在，Windows 直接调即可。**装了 make 的 Windows 机器**也要覆盖 `PY`：
`make PY=.venv/Scripts/python.exe <target>`。

| make 别名 | 直接命令（Windows/Linux 通用；`python` = 你的 venv 解释器） |
|:--|:--|
| `make install` | `pip install -e .` |
| `make dev-install` | `pip install -e ".[dev]"` |
| `make test` | `pytest -v`（快速子集 `pytest -m "not real_api"` / `-m "not slow"`） |
| `make test-coverage` | `pytest --cov=autoinfo --cov-report=term-missing` |
| `make lint` | `ruff check src/ tests/` 然后 `mypy --platform linux src/` ① |
| `make lint-fix` | `ruff check --fix src/ tests/` |
| `make validate DIR=outputs/<domain>` | `python scripts/quality_gate.py outputs/<domain>` |
| `make battery DIR=… [SEMANTIC=1]` | `python scripts/agent_review/battery.py <dir> [--semantic]` |
| `make doc-check` | 三段命令，见 ② |
| `make clean` | 删 `build/ dist/ *.egg-info/` 与各缓存目录（PowerShell `Remove-Item -Recurse -Force`；Git Bash 照旧 `rm -rf`） |
| `make stripe-mock` | `docker compose up -d stripe-mock` |
| `make backup` | `bash scripts/backup-db.sh`（Git Bash 自带 bash） |

① Windows 原生 `mypy src/` 会误报 3 条 POSIX-only 属性（`os.killpg/getpgid/SIGKILL`；运行时有
`os.name == "nt"` 守卫，运行时安全）——加 `--platform linux` 与 ubuntu CI 同一类型契约，**别为消掉它
改产品代码**（`harness-run-facts.md` 坑 6）。

② `make doc-check` = `python -m autoinfo.gov check --json` +
`python scripts/coverage_matrix.py --check-enduser-doc docs/dev/enduser-coverage-matrix.md` +
`python scripts/gen_demo_domains_table.py --check`。改 docs/ 之外还要追加
`python3 scripts/doc_inventory.py` + `python3 scripts/surface_parity.py --check`——
`make doc-check` **不含** doc_inventory，只跑它是最常见的假绿（`harness-run-facts.md`「门禁顺序」）。

## 编码与环境变量

- Python 3.15 之前 Windows 控制台默认编码跟随代码页，CLI/测试遇到 `UnicodeEncodeError` 或乱码时设
  `PYTHONUTF8=1`（CMD `set PYTHONUTF8=1`；PowerShell `$env:PYTHONUTF8 = "1"`）。
- 环境变量三写法（以 LLM key 为例）：
  - PowerShell（当前会话）：`$env:AUTOINFO_LLM_API_KEY = "sk-..."`
  - CMD（当前会话）：`set AUTOINFO_LLM_API_KEY=sk-...`
  - 永久：`setx AUTOINFO_LLM_API_KEY "sk-..."`（setx 之后**新开的**进程才可见，不进当前会话）。
- `.env` 约定：用户级 `~/.autoinfo/.env`（即 `C:\Users\<you>\.autoinfo\.env`），KEY=VALUE、
  **UTF-8 保存**；别用 Windows PowerShell 5.1 的 `>>` 追加——会写成 UTF-16（#847，
  `harness-run-facts.md`）。仓库本地 `.env` 不被读取。

## Windows 已知坑（全量清单见 harness-run-facts.md）

1. **Windows CI ≠ 全量等价**：CI 的 `windows-smoke` job 只覆盖安装 + ruff +
   `mypy --platform linux` + E2E baseline + 小型 Windows 敏感子集；全量测试只在 Linux runner 跑。
2. **`mypy src/` 误报 3 条**：见上表 ①，`--platform linux`。
3. **裸 make 解析错解释器**：`PY ?= python3` 在 Windows 落到系统解释器；覆盖 `PY=` 或直接调 venv 解释器。
4. **e2e 场景测试要 venv Scripts 上 PATH**：场景子进程裸调 `autoinfo` CLI；先激活 venv，或
   `$env:Path = "$PWD\.venv\Scripts;$env:Path"`（bash：`PATH="$PWD/.venv/Scripts:$PATH"`）。
5. **pull 了 release bump ⇒ 刷新 editable 安装**：`pip install -e ".[dev,ebook]"` 后再跑版本相关测试。

## 自检与无 key 岔口

- 机器判定（agent/harness）：`python scripts/agent_ready.py --json` —— venv/依赖/LLM 阶梯/文档门
  一次查完，按 `next_action` 走；能力探针 `python scripts/check_deps.py --json`。
- 人读判定：`autoinfo doctor`（LLM 未配置时输出可行动提示）。
- MCP agent：`diagnose_system()`（结构化健康数据；`AGENTS.md` MUST NOT 表的岔口——CLI harness 与新人
  用上面两条，不走 MCP）。
- 一个 key 都没有 ⇒ 三阶阶梯（细则 [`llm-config.md` §No key at all](llm-config.md)）：
  harness 自带默认模型 → 本机已有 OpenAI 兼容端点（只读）→ 问屏幕前的人类（`blocked:no-llm-key`，
  写清 base_url + key + 模型名）。
