---
title: Preview smoke seed entry
source_url: https://example.com/preview-smoke
source_platform: web
source_type: article
date: 2026-10-25
tags: [preview-smoke]
---

# Preview smoke seed

这条 fixture 的唯一用途：让 preview 冒烟能断言**真实 DB 读取链路**（搜索至少返回 1 条），
而不是只断言"页面能打开"。CI 每次都是全新库，没有它第 3 条断言必然失败。
