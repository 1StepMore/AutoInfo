# AutoInfo — Consumer Output Gap Analysis

> **Date:** 2026-07-26
> **Correction (2026-07-26):** Verified against current codebase. All 16 gaps (G1-G16) remain open as documented. Cross-reference: See `docs/dev/implementation-gaps.md` for feature-level implementation gap audit (back-end, MCP tool, and doc accuracy gaps).
> **Method:** Cross-reference of 5 research reports against AutoInfo current output/delivery capabilities
> **Reports analyzed:**
> - `docs/archive/reports/global-content-paid-research-report-trae.md` — Global content paid research report
> - `docs/archive/reports/综合报告-资讯付费与AI触达研究.md` — Comprehensive report on info payment & AI reach
> - `docs/archive/reports/资讯付费调研报告-2026-hermes.md` — Info payment survey 2026
> - `reports/Agent资讯触达与付费分析-qwen.docx` — Agent info reach & payment analysis
> - `reports/国内外资讯付费意愿调研报告-zhipu.html` — Domestic/foreign info payment willingness survey

---

## Executive Summary

AutoInfo has strong text-based output (Markdown/HTML/JSON/PDF/RSS) but **10 gaps** across 5 dimensions prevent it from meeting consumer expectations identified in the research reports. The 3 critical gaps are: (1) no audio output, (2) no agent-native output format, (3) no monetization pipeline.

---

## Dimension 1: Content Format Support

### Consumer Expectations (from reports)

| Format | Preference | Evidence |
|--------|-----------|----------|
| Text reading | 55% global avg, declining | Reuters Institute DNR 2025/2026 |
| Video | 31%, fast growing (US 55%→72% 2021→2025) | Reuters Institute DNR 2026 |
| Audio/podcast | 14%, stable growth; 42% willing to pay | Reuters Institute DNR 2025 |
| Short video | 75.7% of Chinese knowledge-paying learners | Report data |
| Audio courses | 15% (¥278B market, 192M users) | Report data |
| Text + image columns | 5% (irreplaceable for deep domains) | Report data |

### AutoInfo Current Support

| Format | Digest | Report | Tutorial | Presentation | Export |
|--------|--------|--------|----------|--------------|--------|
| Markdown | ✅ | ✅ | ✅ | ✅ | ✅ |
| HTML | ✅ | ✅ | ⚠️ (MCP claims but only markdown implemented) | ✅ | ❌ |
| JSON | ✅ | ✅ | ⚠️ (same) | ❌ | ✅ |
| PDF | ❌ | ❌ | ❌ | ❌ | ✅ |
| RSS | ❌ | ❌ | ❌ | ❌ | ⚠️ (hidden from MCP schema) |
| **Audio** | **❌** | **❌** | **❌** | **❌** | **❌** |
| **Video** | **❌** | **❌** | **❌** | **❌** | **❌** |
| **Data viz/charts** | **❌** | **❌** | **❌** | **❌** | **❌** |

### Gaps

| # | Gap | Severity | Evidence |
|---|-----|----------|----------|
| G1 | **No audio output** (podcast/audio digest) | 🔴 Critical | 14% user preference, 42% willingness to pay for podcast content. TTS pipeline could render digest text as MP3. Delivery channels (Telegram, Discord) already support file attachments. |
| G2 | **No video output** | 🟡 Medium | 31% preference and fast-growing, but high engineering cost. Notably, premium data terminals (Bloomberg, Wind) don't support video either — mitigates severity for B2B use cases. |
| G3 | **RSS hidden from MCP export schema** | 🟢 Small | `export_kb()` supports RSS (`output.py:324-331`) but MCP schema at `server.py:4617` omits `"rss"` from enum. 1-line fix. |
| G4 | **Tutorial format misdeclaration** | 🟢 Small | MCP declares `format: markdown/html/json` but `output.py:2695` says "only markdown is currently supported". Code-doc mismatch. |

---

## Dimension 2: Delivery Channels & Subscription Reach

### Consumer Expectations (channel importance ranking)

| Rank | Channel | Reach / Importance |
|:----:|---------|-------------------|
| 1 | Social + Video networks | 54% weekly reach (DNR 2026) |
| 4 | **AI chat bot / Agent** | **10% (+3pp YoY, fastest growing)** |
| 5 | Own website / App | 51% (largest direct monetization) |
| 6 | **Push notifications** | **Android CTR 3.95-8.49%, iOS ~3.99%** |
| 7 | **Email Newsletter** | **21.5% open rate** |
| 10 | **RSS / Feed** | **6% active users, but 400M+ podcasts** |
| 13 | **AI Agent (MCP/A2A)** | **2026 new frontier, 200× MCP server growth** |

### AutoInfo Current Delivery Channels

| Channel | Status | Formats | Send Mode |
|---------|--------|---------|-----------|
| SMTP Email | ✅ | Digest Markdown/HTML | Scheduled / On-demand |
| Webhook | ✅ | Any JSON payload | Per-collection |
| REST API | ✅ | JSON | On-demand |
| File Export | ✅ | JSON → file | On-demand |
| Telegram | ✅ | Text + HTML parse | `sendMessage` |
| Discord | ✅ | Content + embeds | Webhook REST |
| WeChat OA | ✅ | Template messages | REST |
| WeChat Work | ✅ | Text/notice | REST |
| DingTalk | ✅ | Robot + App API | REST |
| FeiShu | ✅ | Bot webhook + App | REST |
| **RSS delivery** | **❌** | — | — |
| **Push notification (APNS/FCM)** | **❌** | — | — |
| **Agent-mediated push** | **❌** | — | — |

### Gaps

| # | Gap | Severity | Evidence |
|---|-----|----------|----------|
| G5 | **RSS as a delivery channel doesn't exist** (no scheduled RSS feed generation) | 🟡 Medium | All 400M+ podcasts use RSS. Scheduled `export_kb(format="rss")` could produce a live feed. No `RSSDeliveryChannel` in `delivery/__init__.py`. |
| G6 | **Agent delivery is pull-only** | 🟡 Medium | MCP server lets agents *query*, but no webhook-for-agent for pushes. Perplexity Comet / ChatGPT Tasks pattern (agent subscribes, gets pushed) missing. |
| G7 | **No email newsletter recipient control** | 🟢 Small | `send_email_digest` reads recipients from config only. No per-subscriber list, no Substack-style segmentation. |

---

## Dimension 3: Personalization & Customization

### Consumer Expectations
- Role-aware content (C: student vs practitioner; B: executive vs analyst)
- Domain-aware depth (finance needs data; law needs citations; medical needs evidence levels)
- Frequency control (daily push vs weekly digest vs monthly report)
- Channel preference (email vs RSS vs Telegram vs Agent)

### AutoInfo Current Personalization

| Feature | Status | Location |
|---------|--------|----------|
| `custom_instructions` | ✅ All 4 generate functions | `output.py:1486` |
| `target_audience` | ⚠️ Tutorial/Presentation only (not exposed via MCP) | `output.py:2673` |
| Domain-specific template overrides | ✅ `ProductTemplate` | `output.py:1121` |
| Domain terminology guardrails | ✅ Translation only | `output.py:2358` |
| Quality gate config | ✅ Per-domain | MCP `set_gate_config` |
| **Role-aware digest/report** | **❌** | — |
| **Stored user preference profile** | **❌** | — |
| **A/B output recipes** | **❌** | — |

### Gaps

| # | Gap | Severity | Evidence |
|---|-----|----------|----------|
| G8 | **`target_audience` not exposed through MCP** | 🟡 Medium | `_handle_generate_tutorial` and `_handle_generate_presentation` MCP handlers don't expose `target_audience` param, though underlying `output.py` functions support it. Code-rot: parameter was commented out or never added. |
| G9 | **Digest and report missing role-awareness** | 🟡 Medium | `generate_digest()` and `generate_report()` have no `target_audience` parameter. All outputs use same LLM prompt and template. Workaround: pass via `custom_instructions`. |
| G10 | **No stored user preference profiles** | 🟢 Small | `custom_instructions` is per-call; no `UserProfile` → `output_preferences` connection. EndUserProfile (`end_user.py`) exists but isn't linked to output personalization. |

---

## Dimension 4: AI Agent Integration (2026 New Frontier)

### Consumer Expectations
- Global 10% get news via AI (annual +3pp)
- <25 age group: 17%
- GenAI weekly usage: 34% (18%→34% 2024→2025)
- MCP servers: 50→12,000+ (200× growth)
- Key monetization models: content licensing (Reuters MCP), revenue sharing (Perplexity Comet 80/20), agent subscriptions

### AutoInfo Current Agent Readiness

| Capability | Status | Details |
|-----------|--------|---------|
| MCP Server | ✅ | 114 tools, 32 categories |
| KB for agent retrieval | ✅ | Hybrid search + vector |
| **Agent-native output format** | **❌** | No structured JSON-LD optimized for LLM consumption |
| **Agent subscription/push** | **❌** | Agent cannot "subscribe" to a domain for periodic updates |
| **Content licensing/paywall** | **❌** | No paid-content metering, no subscription gating, no revenue-share model |
| **Webhook for agent notification** | **❌** | Existing webhook sends raw collected data, not structured content |
| **Rate limiting / auth for MCP** | **❌** | No API-key-based access control |

### Gaps

| # | Gap | Severity | Evidence |
|---|-----|----------|----------|
| G11 | **No agent-native output format** | 🔴 Critical | When an agent queries AutoInfo's digest, it gets Markdown or HTML. No structured JSON schema with UUIDs, confidence scores, full source citations, relation graph edges — optimized for LLM re-consumption. Consumer reports show this is the fastest-growing channel. |
| G12 | **No agent subscription mode** | 🟡 Medium | Perplexity Comet (2026) and ChatGPT Tasks (2025) let agents *subscribe* to content. AutoInfo's MCP is pull-only; no webhook-callback mechanism for "push to agent when new digest ready." |
| G13 | **No content licensing pipeline** | 🟡 Medium | Reports show media-AI licensing is the new monetization engine ($60M/y Reddit-Google, $250M/5y News Corp-OpenAI). AutoInfo's source ToS compliance (F46) classifies sources but cannot *negotiate* output usage licensing. |

---

## Dimension 5: Monetization & Pricing Support

### Consumer Expectations
- Subscription: $10-$80/mo consumer, $50K-$500K B2B
- Micro-subscription: $0.25-$15/mo creator
- API/data license: $0.24/1K calls to $60M+/year
- Effect-based pricing (RaaS): emerging
- Substack ecosystem: 8.4M paid subscribers, +68% YoY

### AutoInfo Current Monetization

| Feature | Status | Details |
|---------|--------|---------|
| Product types (RAW/PROCESSED) | ✅ | `product_type` parameter |
| Delivery gate (D1-D3) | ✅ | Quality gates block delivery |
| End user profiles | ✅ | `src/autoinfo/end_user.py` |
| End user subscriptions | ✅ | `src/autoinfo/subscription.py` |
| **Content pricing** | **❌** | No pricing tiers, no free vs premium |
| **Usage metering for billing** | **⏳ Cost metering exists** | Tracks LLM tokens/storage but not linked to billing |
| **Payment processing** | **❌** | No Stripe/Alipay/WeChat integration |
| **Per-product gating** | **❌** | Cannot tag certain outputs as "free" vs "premium" |
| **Freemium content gating** | **❌** | No meter wall, no paywall |

### Gaps

| # | Gap | Severity | Evidence |
|---|-----|----------|----------|
| G14 | **No monetization pipeline** | 🔴 Critical | Frameworks exist (EndUserProfile + Subscription) but nothing to charge with: no Stripe integration, no payment methods, no pricing tiers. AutoInfo can generate world-class digests but cannot charge for them. |
| G15 | **No freemium output gating** | 🟡 Medium | Cannot mark some outputs as "free sample" and others "subscribers only." `ProductTemplate` has no `access_level` field. |
| G16 | **No usage-based billing** | 🟢 Small | Internal `CostMeter` tracks LLM costs but isn't mapped to customer billing metering. |

---

## Gap Priority Matrix

| Rank | Gap | Severity | Effort | Impact | Recommendation |
|:----:|-----|----------|--------|--------|---------------|
| 1 | G1: No audio output | 🔴 Critical | Medium | Unlocks 14% preference + 42% willingness to pay | Add TTS pipeline + podcast RSS delivery |
| 2 | G11: No agent-native format | 🔴 Critical | Low-Med | Unlocks fastest-growing channel (10%+ users, +3pp/y) | Add `_render_agent_json()` + MCP `format="agent"` |
| 3 | G14: No monetization pipeline | 🔴 Critical | High | Revenue generation — project survival | Stripe integration + payment processing |
| 4 | G8: target_audience not in MCP | 🟡 Medium | Low | Directly matches consumer demand for role-aware output | Add param to 2 MCP handlers |
| 5 | G12: No agent subscription mode | 🟡 Medium | Medium | Unlocks "push" agent use case | MCP webhook-for-agent + event model |
| 6 | G15: No freemium gating | 🟡 Medium | Medium | Enables free-to-premium funnel | Add `access_level` to `ProductTemplate` |
| 7 | G5: RSS not a delivery channel | 🟡 Medium | Low | Matches consumer podcast/newsletter expectation | Add `RSSDeliveryChannel` + scheduled feed |
| 8 | G6: Agent delivery pull-only | 🟡 Medium | Medium | Complements G12 | Webhook callback support in MCP |
| 9 | G9: No role-aware digest/report | 🟡 Medium | Low | Matches persona demand | Add `target_audience` to generate_digest/generate_report |
| 10 | G2: No video output | 🟡 Medium | High | 31% preference but high cost | Defer — B2B competitors don't support it either |
| 11 | G13: No content licensing pipeline | 🟡 Medium | High | New monetization engine | Defer — requires legal framework |
| 12 | G10: No user preference profiles | 🟢 Small | Low | Incremental improvement | Link EndUserProfile → output_preferences |
| 13 | G3: RSS hidden from MCP | 🟢 Small | Trivial | Clean up API | 1-line fix to MCP schema |
| 14 | G4: Tutorial format misdeclaration | 🟢 Small | Trivial | API consistency | Fix MCP schema or implement html/json |
| 15 | G7: Newsletter recipient control | 🟢 Small | Low | Incremental | Pass recipients through MCP tool |
| 16 | G16: No usage-based billing | 🟢 Small | Medium | Future revenue | Map CostMeter → billing metering |

---

## Reference Files

| File | Path |
|------|------|
| Output generation engine | `src/autoinfo/output.py` (3289 lines) |
| Delivery channels | `src/autoinfo/delivery/__init__.py` (580 lines) |
| Channel implementations | `src/autoinfo/delivery/{telegram,discord,wechat_oa,wechat_work,dingtalk,feishu}.py` |
| Jinja2 templates | `src/autoinfo/data/templates/{digest,report,tutorial,presentation}.{md,html}.j2` (7 files) |
| MCP server | `src/autoinfo/mcp/server.py` (114 tools) |
| End user profiles | `src/autoinfo/end_user.py` |
| Subscriptions | `src/autoinfo/subscription.py` |
| Cost metering | `src/autoinfo/cost.py` |
| Product types | `src/autoinfo/output.py` (RAW vs PROCESSED, lines 1489, 1736) |
| Research reports | `docs/archive/reports/*.md`, `docs/archive/reports/*.html`, `docs/archive/reports/*.docx` (archived, originally at `reports/`) |
