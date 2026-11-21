# #928 修复验证判定（retail digest 综合路径）

- 日期：2026-11-21 15:54 (+08:00)
- commit：`ac142a46`（fix/928-digest-truncation）
- 判定人：owner:human-agent harness（本机，AUTOINFO_LLM_API_KEY 阶梯第 2 档：本机 OpenAI 兼容端点 spark-x2.6，真模型）
- confidence：**real**（真模型生成；单测部分为 mock，仅证机制/契约）

## 命令

```bash
python scripts/capability_matrix.py --domains retail --only digest:markdown --force \
  --out docs/dev/validation-reports/capability-27x3/issue-928-retail-verify
```

## 每格读数

| 格 | reached | L3 | llm_status | keyed | 产物 |
|:--|:--|:--|:--|:--|:--|
| retail/digest:markdown | L3 | ✅ | llm | keyed | digest-markdown-20261121-075508-410592.md（19624 bytes，l2=pass）|

## 结论

- 修复后综合路径真跑 = keyed L3，`llm_generated=true`，无 `digest_synthesis_empty` 回落，sidecar 无 `llm_failure`（干净通过）。
- 本轮真跑未复现截断（截断是概率性事件）；「截断→检测→升级 max_tokens 重试→成功」的机制由 13 条单测证明（mock 链路，confidence=mock），真跑证明修复无回归且产出 keyed L3。
- 本机缺 AUDIO/VIDEO 能力线（无 ffmpeg/ffprobe/TTS），#928 验收里的 `retail/digest:audio` 单格复跑属媒体线 → code 侧机器执行；本次以共享同一综合路径的 digest:markdown 做真模型验证，记入交接。
- 走法依据：matrix-verdict-policy §2「只重跑红格与新增格」——本轮只跑 retail/digest:markdown 单格，未重跑整批；flaky 统计不变（首跑证据 = 52 格扫，2026-11-21 05:00）。
