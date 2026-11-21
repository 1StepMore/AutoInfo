# #849 Windows 原生全量套件判定（挂死根治证据）

- 日期：2026-11-21 18:13 (+08:00)
- 分支：fix/849-windows-hang（rebase 后，含 #928/#930/#931 内容）
- 判定人：owner:human-agent harness（本机 Windows 原生，AUTOINFO_LLM_API_KEY 阶梯第 2 档存活）
- confidence：**real**（真跑，pytest 机器读数）

## 命令与读数

```bash
python -m pytest -m "not real_api" -q --tb=no
# → 7168 passed, 44 skipped, 4 deselected, 1 failed in 2029s (33:49)
#   唯一红 = tests/validation/test_no_synthetic_kb_residue.py
#           ::test_no_unpromoted_draft_under_wiki_tier_dir
#   = T9 后门草稿（03-Wiki append-only，删除需 owner 显式点名，#887 已登记）
```

修复前基线（#849 issue 原始复现）：3 次在 36% 处挂死、无 summary、asyncio IOCP 循环不可恢复。

## 修复链（三层）

1. **hermetic 门**（tests/conftest.py autouse）：非 real_api 测试的
   litellm.completion/acompletion/embedding 在共享模块边界立即抛错——真实网络调用
   从「挂死 300s+」变「立即报错」（自测 tests/test_hermetic_llm_gate.py）。
2. **timeout 解析**（src/autoinfo/llm.py）：call_with_fallback 的 timeout=None 不再
   直通 litellm 600s 默认；强制解析 config.llm.timeout 或 DEFAULT_LLM_TIMEOUT。
3. **journey CI 语义**（tests/e2e/conftest.py）：journey 测试摘除 env key，引擎
   requires_env 判定（validation.py:2539）与 MCP 分派守卫（server.py:758）与无 key
   CI 逐层同语义；scenario 级诚实 unconfigured（e2e 18 passed + 5 skip）。

## 附带读数

- e2e journey 文件：18 passed, 5 skipped（修复前：1 硬红 journey-kb-promote +
  1 挂死 journey-output-formats）
- build_release_check：19/19（editable install 刷新后）
- KB parity：5/5（2 个诊断跑遗留 t9-kbp 孤儿行经 director 路由清除）
- litellm 远程 cost map 拉取失败（WinError 10054）为本机网络噪音，回落本地备份，不影响判定。

## 边界如实记录

- 死端点场景的 3 次原始复现需死端点机器（goals.md P3 已注明），本机端点存活，
  以「带 key 全量完成 + 门自测 + journey 同语义」为证据；如需死端点复现读数，
  留待 code 侧死端点机器补记。
- T9 草稿红 = owner 门控项，不放宽、不计入修复回归。
