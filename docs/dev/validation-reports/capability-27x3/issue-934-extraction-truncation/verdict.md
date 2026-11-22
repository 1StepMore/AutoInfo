# #934 抽取路径截断升级重试 — 验证记录（2026-11-22）

> PR 补 #934：`llm.py` 抽取路径（`_call_llm` / `_parse_response`）。#934 列的 5 处
> output 侧（report/翻译/CEFR/演示/教程）不在本 PR 范围，仍是 #934 的剩余工作。

## 修了什么

- 截断检测（`finish_reason=length` 或 JSON 未闭合）→ **一次**升级重试
  （4000 → 8000，与 #931 digest 救援同构 ×2）；非截断解析失败保持历史单次尝试
  原预算，宽松契约不变（不再静默吞成空 summary 入库——截断时会真重试）。
- 截断启发式上移为单一实现：`looks_truncated_json` 落在 `llm.py`（parse 层），
  output 层 digest 救援改为从 llm 导入（`_looks_truncated_json` 别名，调用点零改动）。
- `_parse_response` 增加 `errors` 出参，区分"解析失败"与"合法空对象"。

## 验证（全部真跑）

1. **单测**（模拟）：`tests/llm/test_llm.py::TestTruncationEscalation` 4 用例——
   升级重试成功 / 无 finish_reason 未闭合括号也升级 / 非截断失败保持原预算不重试 /
   双重截断仍走宽松空结果不抛异常。33 passed（全文件）。
2. **真模型**（spark-x2.6，机器端点，keyed）：`evidence-run-2026-11-22.json`——
   baseline 正常抽取非空；强制截断（预算 12）→ 升级告警出现 → 8000 重试真跑成功、
   结果非空。端到端成立，零 fake 判定。
3. **回归**：`tests/output/test_digest.py` 65 passed 4 skipped（截断启发式搬家后
   digest 路径不受影响，test_digest 对 `_looks_truncated_json` 的导入经别名续用）。
4. **lint**：ruff 全绿；mypy 21 errors 与 main 基线逐文件一致（本次改动文件 0 新增）。

## 边界与后续

- 本 PR 后 #934 仍 OPEN：5 处 output 侧固定 8000 不查 finish_reason 的静默降级
  （report.py:480、output/__init__.py:4816/5422、presentation.py:495、tutorial.py:514）
  是 #934 的下一手，建议沿用同一 `llm_call_with_truncation_retry` 共用入口思路。
- provenance/sidecar 可见化（`llm_failure` 字段进 process 管道产物）不在本 PR：
  抽取路径的降级当前以 warning 日志可见，跨层 provenance 管道是独立改动。
