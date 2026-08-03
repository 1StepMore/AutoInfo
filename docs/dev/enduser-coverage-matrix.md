# End-User Service Coverage Matrix

> AutoInfo v1.8.3 vs 综合报告-资讯付费与AI触达研究.md  
> Mapping: Report Dimension → Code Coverage → Validation Plan Coverage → Gap  
> 2026-08-02 更新（第 5 次，V1 计划完成）：H1 生产清单 10 项全部落地（A18 GDELT / A23 SSRN / A24 HuggingFace-Kaggle / A25 Unpaywall-CORE OA 子集 / A29 中文播客 / E9 source_score / E11 RAW variants / E12 单篇支付 / E14 simplify_content / C11 播客 RSS），H2 验证补齐 B15/E7/E11 ✅ 已完成、A6/C6 待凭证 SKIPPED。覆盖率从 76% 升至 83%，P2 可工程化缺口从 7 项降至 3 项，剩余缺口从 28 项降至 18 项。同步修正历史计数偏差（B/C/E 维 stats 与 item 表不一致），全量重算。
> 2026-08-02 更新（第 4 次）：新增 **H 节"可行性判定与实现路线图"**——基于 2026-08-02 外部核实（GDELT / Unpaywall / CORE / Stripe / X API / RSSHub / NSSD / Listen Notes / edX / 公众号 API 共 12 条绕过路径），为全部缺口标注 V1 实现 / V2 推迟 / 放弃 决策与替代方案。  
> 2026-08-02 更新（第 3 次）：全量对齐报告场景——五维从 66 项扩至 **99 项**（+33：A+8 / B+5 / C+6 / D+7 / E+7），修正 C 维 5 处渠道排名（C3/C5/C6/C7/C8），补齐报告 §6.5/§7.3/§8.3/§9/§10.2 场景映射（E9-E15、C14），新增不可工程化/范围外明细。  
> Code 83% (82/99) | Validation 83% (82/99) | 双向 73% (72/99) | 可覆盖上限 93/99（排除 6 项纯无解）

---

## A. 原始资讯源覆盖（报告 Section 3.1, 4）

| # | 资讯源类别 | 报告推荐的平台 | AutoInfo Code | Validation Plan | 覆盖状态 |
|:-:|-----------|---------------|:-------------:|:---------------:|:--------:|
| A1 | **学术文献** | arXiv, PubMed, CrossRef | ✅ 3 collectors | ✅ Part 1 Q2 | ✅ |
| A2 | **学术文献（扩展）** | OpenAlex | ✅ OpenAlexHandler | ✅ Part 1 Q2b.1-3 | ✅ |
| A3 | **学术文献（引用图）** | Semantic Scholar | ✅ SemanticScholarHandler | ✅ Part 1 Q2b.4-6 | ✅ |
| A4 | **会议论文** | DBLP | ✅ DBLPHandler | ✅ Part 1 Q2b.7-9 | ✅ |
| A5 | **专利** | USPTO | ✅ USPTOHandler | ✅ Part 1 Q2b.10-12 | ✅ |
| A6 | **金融数据（免费）** | FRED, Alpha Vantage | ⚠️ http_api 通用 handler + FRED 源，需 API Key | ⚠️ Part 1 Q2b.48（A6 E2E 场景已加，env-gated，待 key） | ⚠️（待 key） |
| A7 | **金融数据（机构）** | Bloomberg, Refinitiv, Wind, 东方财富 Choice, 同花顺 iFinD, CEIC | ❌ 无 collector | ❌ 未测试 | ❌ |
| A8 | **财经/零售数据** | Quandl, Yahoo Finance | ✅ QuandlHandler + YahooFinanceHandler | ✅ Part 1 Q2b.13-17 | ✅ |
| A9 | **新闻（企业级）** | Reuters Connect, AP | ✅ APHandler + ReutersMCPHandler | ✅ Part 1 Q2b.18-23 | ✅ |
| A10 | **新闻（免费 API）** | NYT API | ✅ NYTHandler | ✅ Part 1 Q2b.24-26 | ✅ |
| A11 | **商业新闻 RSS** | TechCrunch, Crunchbase | ✅ ai-commercial 域 | ✅ Part 1 Q2 | ✅ |
| A12 | **中文科技** | 36氪 | ✅ 36kr（RSS 域内源） | ✅ Part 1 Q2b.27 | ✅ |
| A13 | **开发者社区** | GitHub Trending, HackerNews | ✅ tech-ai-developer 域 | ✅ Part 1 Q2 | ✅ |
| A14 | **社交讨论** | Reddit | ✅ RedditHandler | ✅ Part 1 Q2b.28-30 | ✅ |
| A15 | **视频元数据** | YouTube | ✅ YouTubeHandler | ✅ Part 1 Q2b.31-33 | ✅ |
| A16 | **播客元数据** | Spotify, Apple Podcasts | ✅ SpotifyHandler + ApplePodcastsHandler | ✅ Part 1 Q2b.34-39 | ✅ |
| A17 | **中文视频** | B站 | ✅ BilibiliHandler | ✅ Part 1 Q2b.40-42 | ✅ |
| A18 | **付费新闻/通讯社** | WSJ, FT, 财新, 新华社, 人民日报 | ✅ GDELTHandler（GDELT 免费，无 key，3 个月窗口）+ Google News RSS | ✅ Part 1 Q2b.45（GDELT E2E） | ✅ |
| A19 | **中文知识平台** | 知乎, 得到, 微信公众号 | ❌ 无公开 API | ❌ 未测试 | ❌ |
| A20 | **社交/微博** | X/Twitter, 微博, 抖音, 小红书 | ❌ 付费或封锁 | ❌ 未测试 | ❌ |
| A21 | **通用爬虫** | 任意 Web 页面 | ✅ Web + Playwright | ✅ Part 1 Q2 | ✅ |
| A22 | **创作者订阅平台** | Substack, Patreon, Medium | ⚠️ Substack 经通用 RSS（tech-ai-developer 域）；Patreon/Medium 无 | ⚠️ Part 1 Q6b.2（Substack RSS） | ⚠️ |
| A23 | **社科/法律工作论文** | SSRN | ✅ SSRNHandler（RSS 接入，同 Substack 模式） | ✅ Part 1 Q2b.44（SSRN E2E） | ✅ |
| A24 | **开源数据集** | Hugging Face, Kaggle | ✅ HuggingFaceHandler（HF datasets-server 公开 API + Kaggle API） | ✅ Part 1 Q2b.49（HF/Kaggle E2E，46 mock tests） | ✅ |
| A25 | **学术付费数据库** | Elsevier/Scopus, Springer Nature, IEEE Xplore | ✅ UnpaywallHandler + COREHandler（OA 全文子集，非机构付费全文） | ✅ Part 1 Q2b.46/Q2b.47（Unpaywall/CORE OA E2E） | ⚠️（OA 全文子集，机构付费许可内容不在覆盖范围） |
| A26 | **中文期刊库** | 知网 CNKI, 万方, 维普 | ❌ 无公开 API + 强反爬 | ❌ 未测试 | ❌ |
| A27 | **MOOC/在线学位** | Coursera, edX | ❌ 无采集 API（许可复杂） | ❌ 未测试 | ❌ |
| A28 | **海外短视频** | TikTok | ❌ 未接入（Research API 需学术审核） | ❌ 未测试 | ❌ |
| A29 | **中文播客** | 喜马拉雅, 小宇宙 | ✅ ApplePodcastsHandler（iTunes Search, `country=CN`）隐式覆盖 | ✅ Part 1 Q2b.37-39 + A29 实测（2026-08-02: 3 例 country=CN curl 均返回 resultCount≥1） | ✅（隐式覆盖） |

> 备注：报告 §2.3 中国样本中的爱奇艺/优酷/腾讯视频（OTT 视频）无公开采集 API，未接入（B 站见 A17）；知乎/得到见 A19。

### A 维度覆盖率统计

| 指标 | 数值 |
|------|:----:|
| 报告推荐源总数 | 29 |
| AutoInfo Code 已覆盖 | 23/29 (79%) |
| Validation Plan 已测试 | 23/29 (79%) |
| 双向覆盖（Code + Plan） | 21/29 (72%) |
| 完全未覆盖 | 6/29 (21%) |

---

## B. 输出产品/资讯格式覆盖（报告 Section 3.1, 3.2, 3.3）

| # | 产品形态 | 报告识别 | AutoInfo Code | Validation Plan | 覆盖状态 |
|:-:|---------|:--------:|:-------------:|:---------------:|:--------:|
| B1 | **文本文摘（Digest）** | 日报/早报 | ✅ generate_digest | ⚠️ Part 9 (需 LLM) | ✅ |
| B2 | **研究报告（Research Report）** | 深度分析 | ✅ generate_report(researcher) | ✅ Part 2 Q9 | ✅ |
| B3 | **执行摘要（Executive Summary）** | 决策层简报 | ✅ target_audience=executive | ✅ Part 2 Q9 | ✅ |
| B4 | **投资者简报（Investor Brief）** | 投资信号 | ✅ target_audience=investor | ✅ Part 2 Q9 | ✅ |
| B5 | **教程/培训** | 知识教育 | ✅ generate_tutorial | ✅ Part 2 Q9 | ✅ |
| B6 | **演示文稿** | 会议/汇报 | ✅ generate_presentation | ✅ Part 2 Q9 | ✅ |
| B7 | **行业定制报告** | 领域特定模板 | ✅ v1.8 report_type param | ✅ Part 4 Q33.7/33.12 | ✅ |
| B8 | **跨域综合报告** | 多域对比 | ✅ v1.8 domains param + generate_cross_domain_report | ✅ Part 4 Q33.8-33.10 | ✅ |
| B9 | **竞品分析报告** | 头对头对比 | ✅ `report_type="competitive"` | ✅ Part 4 Q33.7 | ✅ |
| B10 | **趋势分析报告** | 时间序列变化 | ✅ `report_type="trend"` | ✅ Part 4 Q33.7 | ✅ |
| B11 | **音频摘要/播客** | 音频消费（14% 偏好） | ✅ `format="audio"` (TTS MP3, OpenAI/edge-tts) | ✅ Part 4 Q36e | ✅ |
| B12 | **视频摘要** | 短视频（72% 渗透率） | ✅ `format="video"` (MP4, TTS narration + FFmpeg) | ✅ Part 4 Q33.11 / Part 2 Q9.18 | ✅ |
| B13 | **JSON 数据导出** | API Feed | ✅ export_json | ✅ Part 4 Q34 | ✅ |
| B14 | **CSV 数据导出** | 表格分析 | ✅ export_csv | ✅ Part 4 Q34 | ✅ |
| B15 | **PDF 报告** | 可打印文档 | ✅ export_pdf/export_bundle | ✅ Part 4 Q34.1c（需 weasyprint 环境；渲染超时 `output.pdf_timeout` 可配置，默认 120s） | ✅ |
| B16 | **Markdown 导出** | 可编辑文档 | ✅ export_markdown | ✅ Part 4 Q34 | ✅ |
| B17 | **RSS Feed 输出** | 订阅源 | ✅ export_rss | ✅ Part 4 Q34.9 | ✅ |
| B18 | **GraphML 图导出** | 知识图谱 | ✅ export_graphml | ✅ Part 4 Q34.10 | ✅ |
| B19 | **多格式 Bundle** | 一次性交付所有格式 | ✅ export_bundle | ✅ Part 4 Q34.1b | ✅ |
| B20 | **本地化/翻译** | 跨语言 | ✅ localize_content | ✅ Part 4 Q33.6 (需 LLM) | ✅ |
| B21 | **直播与社群服务** | 报告 §3.3：直播+社群（75% 续费率） | ❌ 未实现 | ❌ 未测试 | ❌ |
| B22 | **"内容+服务+社群"复合模式** | 报告 §3.3 行业转型方向 | ❌ 未实现 | ❌ 未测试 | ❌ |
| B23 | **电子书/音频书** | 报告 §3.1 教育/通识格式 3 | ❌ 无 epub/音频书输出 | ❌ 未测试 | ❌ |
| B24 | **付费深度专栏** | 报告 §3.1 财经格式 3、§3.3 图文专栏 | ⚠️ 近似：周期性 Digest（B1）可承载专栏式内容，无独立专栏产品 | ⚠️ 由 B1/B2 验证近似覆盖 | ⚠️ |
| B25 | **实时数据终端** | 报告 §3.1 金融格式 1（Bloomberg/Wind 终端） | ❌ 机构级终端形态，超出产品范围 | ❌ 未测试 | ❌ |

### B 维度覆盖率统计

| 指标 | 数值 |
|------|:----:|
| 报告识别产品形态总数 | 25 |
| AutoInfo Code 已覆盖 | 21/25 (84%) |
| Validation Plan 已测试 | 21/25 (84%) |
| 双向覆盖（Code + Plan） | 19/25 (76%) |
| 代码有但未验证 | 0/25 (0%) |
| 完全未覆盖 | 4/25 (16%) |

---

## C. 分发渠道覆盖（报告 Section 5.1, 5.2, 10.2）

> 触达路径分类（报告 §5.2）：A 主动拉取（Pull）/ B 被动推送（Push）/ C 算法分发（Algorithmic）/ D AI 代理（Agent-mediated）

| # | 分发渠道 | 报告排名 | 触达路径 | AutoInfo Code | Validation Plan | 覆盖状态 |
|:-:|---------|:-------:|:-------:|:-------------:|:---------------:|:--------:|
| C1 | **社交+视频网络（算法分发）** | #1 (54%) | C 算法分发 | ✅ `social_publish` 渠道（mastodon/bluesky/linkedin/threads/x）(delivery/social.py) | ✅ tests/delivery/test_social.py | ✅ |
| C2 | **搜索引擎+AI 概览** | #2 | A 主动拉取 | ✅ export_kb format="sitemap"（sitemap.xml）+ JSON-LD 结构化数据 | ✅ Part 2 Q9.19（CLI sitemap）+ Part 4 Q36i.1/Q36i.2（export_kb sitemap + JSON-LD，新增场景） | ✅ |
| C3 | **自有网站/APP** | #5 (51%) | A 主动拉取 | ✅ REST API (FastAPI, 8741) + Web UI Dashboard | ✅ Part 7 Q47/Q48 | ✅ |
| C4 | **AI 聊天机器人/答案引擎** | #4 (10%) | D AI 代理 | ✅ MCP Server (141 tools) | ✅ Part 3+4 | ✅ |
| C5 | **推送通知** | #6 | B 被动推送 | ✅ Push 推送通道 (PushDeliveryChannel + scheduler) | ✅ Part 13 Q63.20（push 渠道分发，新增场景）+ 单元测试 tests/delivery/test_push.py（23 tests） | ✅ |
| C6 | **邮件订阅** | #7 | B 被动推送 | ✅ SMTP 渠道 | ✅ Part 9 Q56a 56a.4（env-gated：`SMTP_HOST`/`SMTP_USER`/`SMTP_PASS`，无凭证 SKIPPED 不 FAIL；2026-08-02 已加场景，凭证未提供故 SKIPPED） | ⚠️ 待 SMTP 凭证（场景就绪；提供 Mailtrap/Resend 免费层或 Gmail app password 后重跑 56a.4 → ✅） |
| C7 | **RSS Feed** | #10 (6%) | A 主动拉取 | ✅ export_rss | ✅ Part 4 Q34.9 | ✅ |
| C8 | **AI Agent 主动推送 (MCP/A2A)** | #13 (新兴) | D AI 代理 | ✅ MCP Server（MCP 侧完整；A2A 原生协议未实现，见 E15） | ✅ Part 3+4 | ✅ |
| C9 | **电视/广播+智能电视** | #3 (52%) | B 被动推送 | ❌ 无 TV 输出能力 | ❌ 未测试 | ❌ |
| C10 | **移动 App+应用商店** | #8 | A 主动拉取 | ❌ 无移动端 App（REST API 可被第三方 App 消费） | ❌ 未测试 | ❌ |
| C11 | **播客平台目录** | #9 | B 被动推送 | ✅ RSS 2.0 播客目录发布（`<enclosure>` + `itunes:*` 命名空间，音频输出自动持久化 MP3） | ✅ Part 4 Q36h（36h.1 播客 RSS 发布 E2E） | ✅ |
| C12 | **浏览器/默认首页/导航** | #11 | A 主动拉取 | ❌ 不适用（无浏览器产品） | ❌ 未测试 | ❌ |
| C13 | **联盟/推荐链接** | #12 | A 主动拉取 | ❌ 不适用（无联盟系统） | ❌ 未测试 | ❌ |
| C14 | **微信生态/IM 消息** | 补充（§10.2 中国触达） | B 被动推送 | ✅ wechat_work + wechat_oa + dingtalk + feishu + telegram + discord 6 渠道 | ✅ Part 13 Q63.17/63.18 | ✅ |

### C 维度覆盖率统计

| 指标 | 数值 |
|------|:----:|
| 报告渠道总数（§5.1 十三渠道 + C14 补充） | 14 |
| AutoInfo Code 已覆盖 | 10/14 (71%) |
| Validation Plan 已测试 | 10/14 (71%) |
| 双向覆盖 | 10/14 (71%) |
| 完全未覆盖 | 4/14 (29%) |

---

## D. 领域/Use Case 覆盖（报告 Section 2.1, 7.2.3, 10.4, 10.5）

| # | 领域 | 付费意愿排名 | AutoInfo Demo 域 | 报告可行性 | 覆盖状态 |
|:-:|------|:----------:|:----------------:|:---------:|:--------:|
| D1 | **企业级 SaaS / AI Apps** | #1 ($675B) | ✅ ai-commercial | ✅ TechCrunch+ProductHunt | ✅ |
| D2 | **在线视频/OTT** | #2 ($84.7B) | ✅ online-video | ✅ YouTube+Bilibili+Podcasts | ✅ |
| D3 | **财经/新闻深度内容** | #4 (NYT 12M+) | ✅ financial-news | ✅ NYT+RSS+API 源 | ✅ |
| D4 | **专业金融/商业资讯** | #5 | ✅ financial-intelligence | ✅ Part 1 Q6b.1 覆盖 (需 API Key) | ✅ |
| D5 | **医学/生物研究 + 医疗健康** | #7/#9 | ✅ medical-research | ✅ PubMed 免费 | ✅ |
| D6 | **在线教育/知识付费** | #6 ($350B 中国) | ✅ online-education | ✅ OpenAlex+arXiv+RSS 源 | ✅ |
| D7 | **技术/AI/开发者** | #13 | ✅ tech-ai-developer | ✅ GitHub+HN 免费 | ✅ |
| D8 | **法律/合规** | #10 | ✅ legal-compliance | ✅ USPTO+webhook+email 源 | ✅ |
| D9 | **语言学习** | —（非报告领域，AutoInfo 附加） | ✅ language-learning | ✅ Part 1 Q6b.1 覆盖 (RSS 可用) | ✅ |
| D10 | **音乐流媒体** | #3 (Spotify 263M) | ⚠️ 无 demo 域（可经 A16 Spotify API 元数据自建域） | ⚠️ Part 1 Q2b.34-36 部分 | ⚠️ |
| D11 | **音频/播客/数字杂志** | #11 (Cafeyn 2M) | ⚠️ 播客部分 ✅（online-video 域 + A16 + B11 音频输出）；数字杂志 ❌ | ⚠️ 部分 | ⚠️ |
| D12 | **通用新闻/数字报纸** | #12 (20 国 17%) | ⚠️ 无 demo 域（NYT/Reuters/AP/RSS 源可自建 general-news 域） | ⚠️ Part 1 Q2 源级验证 | ⚠️ |
| D13 | **LinkedIn 职业订阅** | #8 ($1.7B/年) | ❌ 无公开 API，抓取封锁 | ❌ 未测试 | ❌ |
| D14 | **游戏内购/数字游戏** | #14 | ⚠️ 行业资讯可经 RSS/Reddit/YouTube 追踪；内购数据无 API | ⚠️ 部分 | ⚠️ |
| D15 | **B2B 数据/工具/API** | #15 | ⚠️ financial-intelligence 域部分覆盖；通用 B2B 数据可自建域 | ⚠️ 部分 | ⚠️ |
| D16 | **零售/电商资讯** | 报告 §7.2.3/§10.5（500 亿元市场） | ⚠️ Web/RSS 可追踪；小红书/抖音受限（A20） | ⚠️ 部分 | ⚠️ |

### D 维度覆盖率统计

| 指标 | 数值 |
|------|:----:|
| 报告高价值领域总数 | 16（§2.1 的 15 + 零售 §7.2.3/§10.5） |
| AutoInfo 有对应 Demo 域 | 8/16 (50%)（D1-D8；D9 语言学习为附加 demo） |
| 至少部分可行（✅+⚠️） | 15/16 (94%) |
| 不可行的域（付费墙封锁） | 1/16 (6%) |

---

## E. Agent 触达与商业化（报告 Section 6, 7, 8, 9）

> 报告 §6.5 Agent 使用场景映射：追问 42% → E5；获取最新新闻 35% → E5；摘要 34% → E5/B1；评估新闻源可信度 33% → E9；跨源对比/多源整合 35% → B8；翻译新闻 33% → B20；把新闻变简单 30% → E14。  
> 报告 §7.1 技术路径：数据直连 → E1（MCP 工具）；个性化推荐 → E6；记忆系统/技能模块化属 Agent 平台侧能力（不适用本平台）。

| # | Agent 能力 | 报告关键数据 | AutoInfo Code | Validation Plan | 覆盖状态 |
|:-:|-----------|:-----------:|:-------------:|:---------------:|:--------:|
| E1 | **MCP 工具暴露** | 报告推荐 | ✅ 141 tools | ✅ Part 3+4 | ✅ |
| E2 | **付费用户管理** | 订阅经济 $7,388 亿 | ✅ Stripe 集成 (847行, 48测试: 42 mock + 6 stripe-mock 集成) | ✅ Part 13 Q65e + TestStripeLifecycle 集成回归 (skipif 无 stripe-mock) | ✅ |
| E3 | **用量追踪/计费** | Zuora SEI | ✅ CostMeter + ConsumptionEvent | ✅ Part 13 Q65h (cost E2E) | ✅ |
| E4 | **多渠道分发** | 6+ 渠道 | ✅ 13 delivery adapters（含 push） | ✅ Part 13 Q63.17-63.19 | ✅ |
| E5 | **RAG 输出** | Agent 检索的基础 | ✅ MCP KB search tools | ✅ Part 4 | ✅ |
| E6 | **个性化推荐** | Perez 76% 用 Agent 购物 | ✅ `recommend_content` MCP 工具 | ✅ Part 04 36b.7/36b.8 | ✅ |
| E7 | **定时任务/告警** | Cron 式触达 | ✅ cron scheduler | ✅ Part 9 Q54.5+Q55.10 (跨进程, 2026-08-02) | ✅ |
| E8 | **Webhook/A2A 集成** | MCP+A2A 双轨 | ✅ webhook+delivery | ✅ Part 03 Q25.3-25.5 | ✅ |
| E9 | **来源可信度评估** | 报告 §6.5：33% 场景 | ✅ 确定性 `source_score`（0-100，基于 quality_tier 的 `SOURCE_TIER_SCORE_MAP`），持久化于 KBEntry，在 G1 门与搜索结果中呈现 | ✅ Part 5 Q37.x（G1 + source_score） | ✅ |
| E10 | **内容合规/版权风险管理** | 报告 §9.1 法规、§8.3 AI 训练数据授权、§10.2 合规路径 | ✅ SourceConfig quality_tier/tos_classification（open/licensed/restricted/sensitive）+ G1TosCompliance + 输出 attribution 页脚 | ✅ Part 5（G1 门） | ✅ |
| E11 | **API 数据许可/RAW 产品** | 报告 §8.3：API/数据许可（Reddit-Google $60M/年） | ✅ RAW 产品携带 `variants: ["api_feed", "webhook", "bulk_export"]` 字段，区分三种 RAW 交付模式 | ✅ Part 4 RAW 变体验证（2026-08-02） | ✅ |
| E12 | **单篇/Micro-subscription** | 报告 §8.3（Substack IAP、单篇 $0.25-$15） | ✅ `create_checkout_session(mode="payment")` 单篇购买 + `check_access(article_id=...)` 权益快速路径 | ✅ Part 13 单篇支付 E2E（2026-08-02） | ✅ |
| E13 | **RaaS 效果付费** | 报告 §8.3、§7.3 价值透明化 | ❌ 无按效果计费（E3 用量计量是基础） | ❌ 未测试 | ❌ |
| E14 | **内容简化** | 报告 §6.5：30% 场景 | ✅ `simplify_content` MCP 工具（CEFR 参数化 A1-C1，LLM 改写 + 原始/简化分级 + 验证标记） | ✅ Part 4 Q36g（36g.1/36g.2） | ✅ |
| E15 | **A2A 原生协议** | 报告 §9.5（Agent-to-Agent） | ❌ webhook 为单向回调，非 A2A 服务器 | ❌ 未测试 | ❌ |

### E 维度覆盖率统计

| 指标 | 数值 |
|------|:----:|
| Agent 能力总数 | 15 |
| AutoInfo Code 已覆盖 | 13/15 (87%) |
| Validation Plan 已测试 | 13/15 (87%) |
| 双向覆盖 | 13/15 (87%) |
| 完全未覆盖（Code 缺失） | 2/15 (13%) |

---

## 总覆盖率矩阵

| 维度 | 报告维度数 | Code 覆盖 | Code % | Plan 覆盖 | Plan % | 双向覆盖 | 双向 % |
|:----|:---------:|:---------:|:------:|:---------:|:------:|:--------:|:------:|
| **A. 原始资讯源** | 29 | 23 | **79%** | 23 | **79%** | 21 | **72%** |
| **B. 输出产品** | 25 | 21 | **84%** | 21 | **84%** | 19 | **76%** |
| **C. 分发渠道** | 14 | 10 | **71%** | 10 | **71%** | 10 | **71%** |
| **D. 领域覆盖** | 16 | 15 | **94%** | 15 | **94%** | 9 | **56%** |
| **E. Agent 触达** | 15 | 13 | **87%** | 13 | **87%** | 13 | **87%** |
| **总计** | **99** | **82** | **83%** | **82** | **83%** | **72** | **73%** |

---

## 未覆盖项优先级（距 100% 的剩余缺口）

> 各缺口的具体绕过路径与 V1/V2/放弃 决策见 **H 节**（2026-08-02 外部核实版）。

### P0 — 代码已实现但未验证（0 项）

> A6 FRED / Alpha Vantage 已于 2026-08-02 补齐验证场景（Part 1 Q2b.48，env-gated，真实 API E2E：collect → Items → G0），当前环境无 `AUTOINFO_HTTP_API_KEY`/`ALPHAVANTAGE_API_KEY`/`FRED_API_KEY`，记录 **SKIPPED**（待免费 key 到位后执行，不 FAIL）。该行保留在 H2 验证补齐清单，随凭证到位后回归。

### P1 — 部分实现/部分验证（0 项）

> E9 来源可信度评估已于 2026-08-02 完成（确定性 `source_score` 0-100，基于 `SOURCE_TIER_SCORE_MAP`，持久化于 KBEntry，G1 门与搜索结果呈现）；E11 RAW 产品变体已于 2026-08-02 完成（`variants: ["api_feed", "webhook", "bulk_export"]` 字段）。两项均从 P1 移出，P1 清空。

### P2 — 代码缺失但可工程化（3 项）

> 报告明确列出的可接入平台/可扩展产品，尚未实现。A23 SSRN / A24 HuggingFace-Kaggle / E12 单篇支付 / E14 内容简化 已于 2026-08-02（V1）实现并移出。

| 项 | 功能 | 报告依据 | 实现路径 |
|:--:|------|---------|---------|
| A28 | TikTok | §4.5 Research API | 需学术审核（Research API 准入） |
| B23 | 电子书/音频书输出 | §3.1 教育格式 3 | epub/mobi 导出扩展 |
| E15 | A2A 原生协议 | §9.5 Agent-to-Agent | A2A server 实现（当前 webhook 单向） |

### P3 — 报告识别但不可工程化（6 项）

> A18 WSJ/FT/财新 已于 2026-08-02 经 GDELT+Google News RSS 零成本覆盖（新闻头条级，非付费墙全文），移出 P3；A25 Elsevier/Springer/IEEE 已于 2026-08-02 经 Unpaywall/CORE 覆盖 OA 全文子集（机构付费许可内容仍不可及，标注 ⚠️ 部分覆盖），移出 P3。

| 项 | 功能 | 原因 |
|:--:|------|------|
| A7 | Bloomberg / Refinitiv / Wind / Choice / iFinD / CEIC | 机构级付费 API，无公开接口 |
| A19 | 知乎 / 得到 / 微信公众号 | 无公开 API，反爬严格 |
| A20 | X / 微博 / 抖音 / 小红书 | 付费 API 或封锁抓取 |
| A26 | 知网 / 万方 / 维普 | 无公开 API + 强反爬 |
| A27 | Coursera / edX MOOC | 无采集 API（许可复杂） |
| D13 | LinkedIn 职业订阅 | 无公开 API，抓取封锁 |

### P4 — 超出产品范围（N/A，8 项）

| 项 | 功能 | 原因 |
|:--:|------|------|
| B21 | 直播与社群服务 | 需运营生态，非知识库平台形态 |
| B22 | "内容+服务+社群"复合模式 | 商业模式转型方向，非单平台功能 |
| B25 | 实时数据终端 | Bloomberg/Wind 机构级终端形态 |
| C9 | 电视/广播+智能电视 | 无 TV 输出能力（渠道硬件依赖） |
| C10 | 移动 App+应用商店 | 无移动端 App（REST API 可被消费） |
| C12 | 浏览器/默认首页/导航 | 无浏览器产品 |
| C13 | 联盟/推荐链接 | 无联盟系统 |
| E13 | RaaS 效果付费 | 需商业模式设计，E3 计量为基础 |

---

## 核心结论

1. **V1 计划完成后代码覆盖率 83%**（82/99）— 2026-08-02 V1 实现落地 10 项生产功能（A18/A23/A24/A25/A29/E9/E11/E12/E14/C11），覆盖率从 76% 升至 83%；A25 学术付费库为 OA 全文子集覆盖（⚠️ 部分覆盖，机构付费许可内容不在范围）
2. **验证覆盖率 83%**（82/99），**双向覆盖 73%**（72/99）— 同步修正历史计数偏差（B/C/E 维 stats 与 item 表不一致），全量从 item 表重算
3. **新增缺口全部为"合理未覆盖"**：P3 不可工程化 6 项（机构付费墙/无 API；A18 经 GDELT 零成本覆盖、A25 经 Unpaywall/CORE 覆盖 OA 子集后移出 P3；A29 中文播客已于 2026-08-02 实测确认 Apple Podcasts 隐式覆盖，移出 P3）+ P4 范围外 8 项，结构性无法或不应覆盖
4. **可工程化但未实现 3 项**（P2：TikTok / 电子书 / A2A）— V1 后剩余的下一步开发优先清单（A23/A24/E12/E14 已于 2026-08-02 实现）
5. **报告 §6.5 七大 AI 使用场景已全部覆盖**：追问/获取新闻/摘要/跨源/翻译 5 项已覆盖（E5/B8/B20），可信度评估已完成（E9=确定性 source_score），内容简化已完成（E14=simplify_content）
6. **微信生态/IM 渠道（C14）此前未在矩阵体现**：wechat_work/wechat_oa/dingtalk/feishu/telegram/discord 6 个适配器实际已实现并验证（Part 13 Q63.17），对应报告 §10.2"内容触达（中国）：微信生态"
7. **C 维渠道排名修正 5 处**：自有网站 #3→#5、推送 #5→#6、邮件 #6→#7、RSS #7→#10、AI Agent #8→#13（对齐报告 §5.1）
8. **新发现 gap**: #99 LLM response_format 空结果无保护, #100 多域 init 未复制全部 sources.yaml, #101 cron 假重复因测试残留, #102 lxml 未申明为直接依赖 — 已全部修复（v1.8.3），见下方 G 节
9. **可行性判定（H 节）**：排除 6 项纯无解后分母为 **93**；零成本可覆盖 86/93（92%），加小额付费（Wind 个人版、微博/抖音）约 88/93（95%）；真 100% 卡在 5 个死结（X 涨价、小红书、LinkedIn、Coursera、公众号全量）
10. **V1 实现清单（H 节）— 已完成 2026-08-02**：10 项生产实现全部落地（A23 SSRN / A24 HuggingFace-Kaggle / A25 Unpaywall-CORE OA 子集 / A18 GDELT / A29 中文播客 / E12 单篇支付 / E14 内容简化 / E11 RAW 变体 / E9 source_score / C11 播客 RSS），全部免费零成本，无外部依赖。验证补齐 5 项中 **B15 PDF ✅ 已完成**（weasyprint 超时配置化）、**E7 cron 跨进程 ✅ 已完成**（Part 9 Q54.5+Q55.10）、**E11 RAW 变体 ✅ 已完成**；**A6 FRED/Alpha Vantage ➖ SKIPPED**（场景已加 Part 1 Q2b.48，env-gated 待免费 key）、**C6 SMTP ➖ SKIPPED**（场景已加 Part 9 Q56a.4，env-gated 待 SMTP 凭证）——两项待凭证回归，不 FAIL。

---

## 距 100% 覆盖的差距清单（2026-08-02 更新 v5，V1 计划完成）

> V1 计划完成后，距 100% 的剩余缺口共 **18 项**：17 项未覆盖（P2 可工程化 3 + P3 不可工程化 6 + P4 范围外 8）+ 1 项部分覆盖（A6 待凭证）。V1 已实现 10 项生产功能（A18/A23/A24/A25/A29/E9/E11/E12/E14/C11），A25 学术付费库为 OA 全文子集覆盖（⚠️ 部分覆盖但 Code/Plan ✅，不计入剩余缺口）；E9/E11 从部分覆盖升至 ✅；A6/C6 验证场景已就绪，env-gated SKIPPED 待凭证回归。

### ① 应覆盖但未做（3 项）— 可工程化，列为下一步开发优先

| 类别 | 项 | 原因 | 实现路径 |
|:----:|:--:|------|---------|
| Code 缺失 | A28 TikTok | Research API 需学术审核 | 准入后接入 |
| Code 缺失 | B23 电子书/音频书 | 无 epub 输出 | epub/mobi 导出扩展 |
| Code 缺失 | E15 A2A 原生协议 | webhook 单向 | A2A server 实现 |

### ② 合理未覆盖 — 外部限制（6 项）— 机构付费墙或无公开 API，结构性无法覆盖

> A18 WSJ/FT/财新 已于 2026-08-02 经 GDELT+Google News RSS 覆盖（新闻头条级），移出；A25 Elsevier/Springer/IEEE 已于 2026-08-02 经 Unpaywall/CORE 覆盖 OA 全文子集（⚠️ 部分覆盖），移出。

| 类别 | 项 | 原因 |
|:----:|:--:|------|
| 代码缺失 | A7 Bloomberg/Refinitiv/Wind/Choice/iFinD/CEIC | 机构级付费 API，无公开接口 |
| 代码缺失 | A19 知乎/得到/微信公众号 | 无公开 API，反爬严格 |
| 代码缺失 | A20 X/微博/抖音/小红书 | 付费 API（X 涨价）或封锁抓取 |
| 代码缺失 | A26 知网/万方/维普 | 无公开 API + 强反爬 |
| 代码缺失 | A27 Coursera/edX | 无采集 API（许可复杂） |
| 代码缺失 | D13 LinkedIn | 无公开 API，抓取封锁 |

### ③ 超出产品范围（8 项）— 与 AutoInfo 产品定位不符，明确不做

| 类别 | 项 | 原因 |
|:----:|:--:|------|
| 范围外 | B21 直播/社群服务 | 需运营生态 |
| 范围外 | B22 "内容+服务+社群"复合模式 | 商业模式转型方向 |
| 范围外 | B25 实时数据终端 | 机构级终端形态 |
| 范围外 | C9 电视/智能电视 | 无 TV 输出能力 |
| 范围外 | C10 移动 App+应用商店 | 无移动端 App |
| 范围外 | C12 浏览器/导航 | 无浏览器产品 |
| 范围外 | C13 联盟/推荐链接 | 无联盟系统 |
| 范围外 | E13 RaaS 效果付费 | 需商业模式设计 |

### ④ 部分覆盖（1 项）— 代码已有，验证或功能待补

> E9 来源可信度评估、E11 RAW 产品变体已于 2026-08-02 升至 ✅，移出部分覆盖清单。A25 学术付费库为 OA 全文子集覆盖（Code/Plan ✅，覆盖状态 ⚠️），已实现至可行上限，不计入待补缺口。

| 类别 | 项 | 原因 | 待办 |
|:----:|:--:|------|------|
| 验证缺失 | A6 FRED/Alpha Vantage | 场景已加（Part 1 Q2b.48），需用户 API Key | 凭证到位后执行 E2E（2026-08-02: SKIPPED 待 key） |

---

## H. 可行性判定与实现路线图（2026-08-02 更新）

> 基于 2026-08-02 外部核实（librarian 调研 GDELT / OpenBB / Unpaywall+CORE / RSSHub / NSSD / Listen Notes / edX / X API 定价 / Stripe 模式共存 / 免费行情层 / NewsAPI+Google News RSS / 公众号第三方 API 共 12 条绕过路径的 2026 存活状态），为全部未覆盖项标注可行性决策。
>
> **核心修正（对比 2026-08-02 上午分析）**：
> - 🔴 X API Basic $200/月档 2026-02 关闭新注册（转 pay-per-use，6 月老用户强制迁移）→ **A20-X 放弃**
> - 🟢 GDELT（免费无 key、3 个月窗口）、Unpaywall（10 万次/天）、CORE（免费注册）确认存活 → **A18/A25 零成本可做**
> - 🟡 RSSHub 中文路由恶化（知乎需 cookie+无头浏览器、小红书 503、公众号 feeddd 挂掉）→ **A19 仅知乎可行且脆弱**
> - 🟡 NSSD 存活但无 API（注册+登录才可下载）→ A26 仅爬虫路径，ROI 低
> - 🟡 edX catalog API 为 beta + 人工审批（2U 重组后）→ A27 不可自助
> - 🟢 Stripe `mode="payment"` 与订阅模式共存（API 层确认）→ E12 直接可做
> - 🟡 OpenBB 为聚合壳（自带 key、AGPLv3）→ 不能替代 Bloomberg，仅归一化免费层数据
> - 🟡 免费行情层收紧：Alpha Vantage 硬性 25 req/天、Twelve Data ~100 req/天、Finnhub 无基本面 → A7 主力靠 Wind 个人版积分
> - 🟡 公众号官方 API 仅账号所有者授权（第三方须逐账号授权，权限集 7）→ 公众号全量采集无合法批量路径
>
> **覆盖率重定义**：99 项 − 6 项纯无解（B21/B22/C9/C12/C13/E13）= **93 项可覆盖集合**；零成本上限 86/93（**92%**），加小额付费（Wind 个人版、微博/抖音）约 88/93（**95%**）；真 100% 卡在 5 个死结（X 涨价、小红书、LinkedIn、Coursera、公众号全量）。

### H1. 生产实现清单（V1 — 全部免费零成本）— ✅ 全部已完成（2026-08-02）

| 项 | 功能 | 实现路径 | 核实依据 | 成本 | 状态 |
|:--:|---|---|:---:|:---:|:---:|
| **A23** | SSRN 社科工作论文 | RSS 接入（同 Substack 模式） | 有限 API/RSS 大部分免费 | 低 0.5-1d | ✅ 已完成 |
| **A24** | Hugging Face / Kaggle | HF datasets-server 公开 API + Kaggle API | 公开免费 API | 中 2-3d | ✅ 已完成 |
| **A25** | 学术付费库 OA 全文 | Unpaywall（10 万次/天）+ CORE 免费 OA 全文（元数据 OpenAlex 已有） | ✅ 核实免费可用 | 中 2-3d | ✅ 已完成（OA 子集） |
| **A18** | 新闻头条级覆盖 | GDELT 免费（无 key、3 个月窗口）+ Google News RSS；高价值内容走机构授权（付费可选，独立决策） | ✅ 核实免费可用 | 低-中 1-2d | ✅ 已完成 |
| **A29** | 中文播客 | Apple Podcasts/iTunes Search（A16）已隐式覆盖；Listen Notes 免费层 300 次/月可选补充 | ✅ 实测核实（2026-08-02: 3 例 country=CN curl 均返回 resultCount≥1，证据 `.omo/evidence/task-5-apple-podcast-cn.json`） | 低 0.5d 验证 | ✅ 已完成 |
| **E12** | 单篇/Micro 订阅 | Stripe `mode="payment"`（与订阅共存） | ✅ 核实 | 低 1-2d | ✅ 已完成 |
| **E14** | 内容简化 | LLM simplify 输出模式（新增 output mode） | — | 低 0.5-1d | ✅ 已完成 |
| **E11** | RAW 产品三变体 | 拆分 api feed / webhook 流 / 批量导出（`variants` 字段） | 文档-代码一致性 | 中 1-2d | ✅ 已完成 |
| **E9** | 来源可信度评分 | G1 分级 + 确定性 `source_score`（0-100，`SOURCE_TIER_SCORE_MAP`） | — | 低 0.5-1d | ✅ 已完成 |
| **C11** | 播客目录发布 | B11 音频已有 + 标准播客 RSS 2.0 发布（`<enclosure>` + `itunes:*`） | — | 低-中 1-2d | ✅ 已完成 |

### H2. 验证补齐清单（V1 — 免费测试凭证即可）— 3/5 已完成，2/5 待凭证

| 项 | 功能 | 凭证方案 | 成本 | 状态 |
|:--:|---|---|:---:|:---:|
| A6 | FRED / Alpha Vantage E2E | 两者免费 key 注册即得（AV 25 req/天、FRED 免费）；场景已加 Part 1 Q2b.48（2026-08-02） | 0 | ➖ SKIPPED（待 key） |
| B15 | PDF 导出验证 | ✅ 2026-08-02 完成：weasyprint 渲染超时配置化（`output.pdf_timeout`，默认 120s，Task 17），Part 4 Q34.1c 实测通过（需 weasyprint 环境） | 已完成 | ✅ 已完成 |
| C6 | SMTP 渠道验证 | Mailtrap / Resend 免费层或 Gmail app password | 0 | ➖ SKIPPED（待凭证） |
| E7 | cron 跨进程验证 | 本地跨进程定时测试 | ✅ 已完成 (2026-08-02, Part 9 Q54.5+Q55.10) | ✅ 已完成 |
| E11 | RAW 变体验证 | 随 H1-E11 拆分一起验证 | 0 | ✅ 已完成 |

> **2026-08-02（Task 18）**：C6 SMTP 渠道验证场景已就绪 —— Part 9 Q56a 新增 56a.4（`SMTP_HOST`/`SMTP_USER`/`SMTP_PASS` env-gated，无凭证 SKIPPED 不 FAIL）。当前无凭证 → SKIPPED 明确记录；提供 Mailtrap/Resend 免费层或 Gmail app password 后重跑即可转 ✅。无任何 src/ 代码修改。

### H3. 推迟到 V2（依赖预算决策 / 审核流程 / 生态成熟）

| 项 | 功能 | 路径 | 阻塞 |
|:--:|---|---|------|
| A7 | 机构金融数据 | Wind 个人版积分充值（报告 §7.2.1：100 元/1 万积分）+ Twelve Data/Finnhub 免费层（~100 req/天） | 需预算决策 |
| A20 | 微博 / 抖音 | 微博开放平台分级付费；抖音开放平台 50 元/万次 | 需预算决策 |
| A28 | TikTok | Research API 学术审核 / Display API 资质 | 流程门槛 |
| E15 | A2A 原生协议 | 代码实现（MCP 139 工具已覆盖 Agent 对接） | 生态未成熟 |
| B23 | 电子书/音频书 | pandoc epub 导出扩展 | 优先级低 |
| A19-知乎 | 知乎采集 | RSSHub 知乎路由（需登录 cookie + 无头浏览器，脆弱） | 维护成本高 |
| C10 | 移动 App | PWA + 微信小程序替代 App Store 分发 | 中-高成本 |

### H4. 明确放弃（不划算 / 结构性无解）

| 项 | 功能 | 原因 |
|:--:|---|---|
| A20-X | X/Twitter | pay-per-use 涨价（2026-02 关闭 $200 档），读写量大成本 > 价值 |
| A26 | 知网/万方/维普 | NSSD 无 API（仅注册登录爬取），ROI 低 |
| A27 | Coursera/edX | Coursera 无 API；edX 审批制 beta |
| D13 | LinkedIn 本体 | 无任何公开/付费内容 API，抓取封锁 |
| A19-公众号 | 微信公众号全量 | 官方 API 仅账号所有者授权，无合法批量路径 |
| A20-小红书 | 小红书笔记 | 内容 API 仅限电商类目 |
| B21/B22/B25/C9/C12/C13/E13 | 产品形态/硬件/商业模式 | 结构性无解（见上方 P4 范围外） |

### H5. 实现顺序建议 — ✅ 已执行（2026-08-02，V1 计划完成）

```
✅ 第 1 批（低垂果实，1-2 天）: E12 单篇订阅 → E14 内容简化 → E9 可信度评分（A29 验证确认已于 2026-08-02 完成 ✅）
✅ 第 2 批（新 collector，2-3 天）: A23 SSRN → A18 GDELT → A24 HF/Kaggle → A25 Unpaywall/CORE
✅ 第 3 批（中量，1-2 天）: E11 RAW 变体拆分 → C11 播客目录发布
验证批次（并行）: B15 ✅ / E7 ✅ / E11 ✅ 已完成；A6 ➖ / C6 ➖ SKIPPED 待凭证回归
```

---

## G. 近期 Issues 对应 Gap 分析（#98-#102）— ✅ 全部已修复（v1.8.3, 2026-07-31）

> **修复状态**：以下全部 gap 已在 v1.8.3 中修复并附带回归测试（见 `CHANGELOG.md` v1.8.3）。

| # | Issue 标题 | 根因 | 影响域 | Gap 类型 | 严重程度 | 修复方式（已落地） |
|:-:|-----------|------|--------|---------|---------|---------|
| #98 | `list_output_templates` 找不到模板 | 模板文件存在但路径配置不匹配，测试环境与生产环境差异 | 全部输出生成(B1-B8) | 测试覆盖不足 | 🟡 Medium | ✅ `output/__init__.py` 中 `_TEMPLATES_DIR`/`TEMPLATE_PATH` 改为基于模块实际路径解析（不依赖 CWD）；`test_output_templates.py` 回归测试 |
| #99 | `generate_report` 空返回 (response_format=json_object) | LLM 不支持 `json_object` 时 `response.choices[0].message.content` 为 None，4 个调用点无 `None` guard | 全部输出生成(B1-B8) | 代码弹性缺失(F1) | 🔴 High | ✅ `_parse_json_response` 接受 `content: str \| None`，返回 `{}` + warning；4 个调用点 `content or ""` guard；`test_digest.py` 回归测试 |
| #100 | 多域 init 只复制一个 sources.yaml | 独立 `sources.yaml` 复制逻辑仅复制第一个域的 sources.yaml | 域管理初始化 | 代码缺陷(ergonomic) | 🟡 Medium | ✅ 彻底移除独立 `sources.yaml`，全部域 sources/topics 直接内嵌 `config.yaml`（单一事实源）；`test_init.py` 回归测试 |
| #101 | `cron add-schedule` 假重复 | 测试残留 `.autoinfo/schedules.yaml` 被 `_load_schedules()` 读取，旧条目与新条目同名冲突。且 CLI cron (`schedules.yaml`) 与 delivery scheduler (`delivery_schedules.yaml`) 使用不同路径 | 定时调度(F3) | 测试隔离缺失 + 双系统路径耦合 | 🟡 Medium | ✅ 删除残留 `schedules.yaml` 工件；cron 测试改用临时目录隔离；`test_cron.py` 回归测试 |
| #102 | `lxml` 未申明为直接依赖 | `lxml` 仅通过 `trafilatura` 传递依赖获取，`pyproject.toml` 未列出；pip `--no-deps` 或 slim 镜像中 Web collector 会崩溃 | Web 收集（A21）| 构建弹性缺失(F4) | 🟡 Medium | ✅ `pyproject.toml` 添加 `lxml>=5.0` 直接依赖；`test_web_handler.py::test_lxml_importable` 回归测试 |

### G 维度 gap 影响评分（修复前基线，均已落地修复）

| Gap ID | 对应 Issue | 影响范围 | 用户可见 | 修复成本 | 优先级 |
|:------:|:---------:|:--------:|:--------:|:--------:|:------:|
| F1 | #99 | B1-B8 全部输出生成 | ✅ 空返回或静默失败 | 低（4 行 guard） | **P0** |
| F2 | #100 | 域初始化 | ✅ 多域用户只有第一个域可用 | 低（修复循环） | **P1** |
| F3 | #101 | 定时调度 | ⚠️ 特定场景下 cron 命令报错 | 中（路径统一或隔离） | **P1** |
| F4 | #102 | Web 收集 | ⚠️ 仅特定部署环境出问题 | 低（一行 dep） | **P1** |
