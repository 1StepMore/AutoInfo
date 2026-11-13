# ACCEPTED GAPS — 已接受的环境限制台账

> 本台账登记**外部环境限制导致的不可测项**：不是产品缺陷，而是当前环境（离线 / 缺系统依赖 /
> 无外部服务凭证）下无法真实执行、且修它超出产品代码范围的能力。每条注明缺什么、影响哪些
> 读数、登记日期与证据。与 `docs/dev/DEBT.md`（技术债，需要产品工作偿还）互补：本台账的条目
> 只随环境变化（联网 / 装依赖 / 有凭证）自动解除，不排期。

| ID | 缺什么 | 影响读数 | 登记日期 | 证据 |
|---|---|---|---|---|
| GAP-VIDEO-CDN | `cdn.jsdelivr.net` 可达性：HyperFrames 渲染模板（`src/autoinfo/output/video_assets/templates/*.j2`）在渲染期从该 CDN 加载 GSAP 3.14.2，不 vendor 进仓库 | `tests/output/test_video_integration.py::TestRealRender::test_real_render_smoke` 在离线环境读数为 `SKIPPED`，reason 以 `blocked-no-cdn:` 开头（#780 修复后口径）；联网且有完整渲染链（bun + ffmpeg + 可启动的 headless Chrome）时真跑 | 2026-11-13 | issue #780：同一失败在旧 main 末态 `8b31fca9` 的 worktree 对照中复现（非回归）；渲染器报 `sub_timeline_script_failure`（GSAP 加载失败） |
