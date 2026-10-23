"""MCP tool schemas — Output, export/import, email, custom extraction (13 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from mcp.types import Tool


def build_tools() -> list[Tool]:
    """Return the 13 schemas for this module, in registration order."""
    return [
        # -- Output (7) ------------------------------------------------------
        Tool(
            name="list_output_templates",
            description="List available output templates for a domain. Each template includes access_level (free/premium/enterprise) for freemium gating (G15).",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (optional)",
                        "default": "",
                    },
                    "user_id": {
                        "type": "string",
                        "description": (
                            "Optional end-user ID for tier-based filtering. "
                            "When set, only templates accessible to this user "
                            "are returned. When omitted, all templates are returned."
                        ),
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="generate_digest",
            description=(
                "Compile a periodic digest summarizing recent KB entries for "
                "a domain over a chosen period (daily, weekly, monthly). "
                "Default markdown; also html, json, agent (JSON-LD), and "
                "audio MP3. Optional recipients emails the digest directly; "
                "max_items, include_stale, and target_audience tailor "
                "content; product supports magazine-digest."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "period": {
                        "type": "string",
                        "description": "Digest period: daily, weekly, monthly",
                        "default": "weekly",
                        "enum": ["daily", "weekly", "monthly"],
                    },
                    "format": {
                        "type": "string",
                        "description": (
                            "Output format: markdown, html, json, agent, audio, epub, audiobook"
                        ),
                        "default": "markdown",
                        "enum": [
                            "markdown",
                            "html",
                            "json",
                            "agent",
                            "audio",
                            "video",
                            "epub",
                            "audiobook",
                        ],
                    },
                    "custom_instructions": {
                        "type": "string",
                        "description": "Optional custom instructions to tailor the output content",
                        "default": "",
                    },
                    "target_audience": {
                        "type": "string",
                        "description": 'Optional target audience description to tailor output tone and depth (e.g. "healthcare professionals", "general public")',
                        "default": "",
                    },
                    "include_stale": {
                        "type": "boolean",
                        "description": "Include stale entries in the digest (default: false). When false, entries below the domain freshness threshold are excluded.",
                        "default": False,
                    },
                    "recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of email recipient addresses for direct digest delivery",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user ID for preference-based personalization. When provided, stored preferences (target_audience, format, max_items) are auto-loaded from the user's profile.",
                        "default": "",
                    },
                    "max_items": {
                        "type": "integer",
                        "description": "Optional maximum number of KB entries to include (default: 0 = use built-in limit of 200). Can be auto-set from stored user preferences when user_id is provided.",
                        "default": 0,
                    },
                    "product": {
                        "type": "string",
                        "description": (
                            "Optional product name from the PRODUCT_TEMPLATES registry "
                            "(e.g. magazine-digest, premium-briefing, enterprise-briefing, "
                            "column). When provided, the digest is rendered through that "
                            "product's template family (e.g. magazine-digest.md.j2). "
                            "Valid products: digest, report, tutorial, presentation, "
                            "premium-briefing, column, magazine-digest, enterprise-briefing."
                        ),
                        "enum": [
                            "digest",
                            "report",
                            "tutorial",
                            "presentation",
                            "premium-briefing",
                            "column",
                            "magazine-digest",
                            "enterprise-briefing",
                        ],
                    },
                    "language": {
                        "type": "string",
                        "description": (
                            "Optional ISO-639 language code (e.g. 'zh', 'en'; alias/"
                            "case tolerant: 'zh_CN', '中文', 'en-US' all match). When "
                            "set, only entries whose detected language matches are "
                            "included, so the digest never mixes languages (issue #309)."
                        ),
                        "default": "",
                    },
                    "ref_limit": {
                        "type": "integer",
                        "description": (
                            "Optional maximum number of KB references to render "
                            "(default: 60; issue #11). References are sorted by "
                            "(has non-empty summary, relevance_score) and capped "
                            "at this limit at the context-build site."
                        ),
                        "default": 60,
                    },
                    "persist": {
                        "type": "boolean",
                        "description": "When true, write the generated artifact to outputs/<domain>/ and return its persisted_path in the envelope (default: false).",
                        "default": False,
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="generate_report",
            description=(
                "Produce a deep structured report analyzing collected items "
                "for a domain over a period (daily, weekly, monthly). "
                "Default markdown; also json, html, agent (JSON-LD), audio, "
                "epub, audiobook, video. report_type switches industry, "
                "competitive, trend, daily-briefing, or column templates; "
                "product supports premium-briefing and enterprise-briefing."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "format": {
                        "type": "string",
                        "description": (
                            "Output format: markdown, json, html, agent, audio, epub, audiobook"
                        ),
                        "default": "markdown",
                        "enum": [
                            "markdown",
                            "json",
                            "html",
                            "agent",
                            "audio",
                            "video",
                            "epub",
                            "audiobook",
                        ],
                    },
                    "period": {
                        "type": "string",
                        "description": "Report period: daily, weekly, monthly",
                        "default": "monthly",
                        "enum": ["daily", "weekly", "monthly"],
                    },
                    "custom_instructions": {
                        "type": "string",
                        "description": "Optional custom instructions to tailor the output content",
                        "default": "",
                    },
                    "target_audience": {
                        "type": "string",
                        "description": 'Optional target audience description to tailor output tone and depth (e.g. "healthcare professionals", "general public")',
                        "default": "",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional end-user ID for freemium access gating (G15). Premium reports are blocked for non-subscribers.",
                        "default": "",
                    },
                    "report_type": {
                        "type": "string",
                        "description": "Report type: standard (default), industry, competitive, trend, daily-briefing, column",
                        "default": "standard",
                        "enum": [
                            "standard",
                            "industry",
                            "competitive",
                            "trend",
                            "daily-briefing",
                            "column",
                        ],
                    },
                    "product": {
                        "type": "string",
                        "description": (
                            "Optional product name from the PRODUCT_TEMPLATES registry "
                            "(e.g. premium-briefing, enterprise-briefing, column). When "
                            "provided, the report is rendered through that product's "
                            "template family. Valid products: digest, report, tutorial, "
                            "presentation, premium-briefing, column, magazine-digest, "
                            "enterprise-briefing."
                        ),
                        "enum": [
                            "digest",
                            "report",
                            "tutorial",
                            "presentation",
                            "premium-briefing",
                            "column",
                            "magazine-digest",
                            "enterprise-briefing",
                        ],
                    },
                    "language": {
                        "type": "string",
                        "description": (
                            "Optional ISO-639 language code (e.g. 'zh', 'en'; alias/"
                            "case tolerant: 'zh_CN', '中文', 'en-US' all match). When "
                            "set, only entries whose detected language matches are "
                            "included, so the report never mixes languages (issue #309)."
                        ),
                        "default": "",
                    },
                    "ref_limit": {
                        "type": "integer",
                        "description": (
                            "Optional maximum number of KB references to render "
                            "(default: 60; issue #11). References are sorted by "
                            "(has non-empty summary, relevance_score) and capped "
                            "at this limit at the context-build site."
                        ),
                        "default": 60,
                    },
                    "persist": {
                        "type": "boolean",
                        "description": "When true, write the generated artifact to outputs/<domain>/ and return its persisted_path in the envelope (default: false).",
                        "default": False,
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="generate_cross_domain_report",
            description=(
                "Generate a synthesis report across multiple domains, "
                "connecting findings and identifying cross-domain trends. "
                "Returns markdown by default; also supports json, html, "
                "agent (JSON-LD), audio, epub, and audiobook.  "
                "At least 2 domains are required.  Period: daily, weekly, monthly."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": 'List of domain names to synthesize across (e.g. ["medical-research", "ai-commercial"]). At least 2 required.',
                    },
                    "format": {
                        "type": "string",
                        "description": (
                            "Output format: markdown, json, html, agent, audio, epub, audiobook"
                        ),
                        "default": "markdown",
                        "enum": [
                            "markdown",
                            "json",
                            "html",
                            "agent",
                            "audio",
                            "video",
                            "epub",
                            "audiobook",
                        ],
                    },
                    "period": {
                        "type": "string",
                        "description": "Report period: daily, weekly, monthly",
                        "default": "monthly",
                        "enum": ["daily", "weekly", "monthly"],
                    },
                    "target_audience": {
                        "type": "string",
                        "description": 'Optional target audience description to tailor output tone and depth (e.g. "healthcare professionals", "general public")',
                        "default": "",
                    },
                    "report_type": {
                        "type": "string",
                        "description": "Report type: standard (default), industry, competitive, trend, daily-briefing, column",
                        "default": "standard",
                        "enum": [
                            "standard",
                            "industry",
                            "competitive",
                            "trend",
                            "daily-briefing",
                            "column",
                        ],
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user ID for preference-based personalization. When provided, stored content_preference (raw_only / processed_only / both) is auto-loaded and KB entries are tier-filtered accordingly.",
                        "default": "",
                    },
                    "language": {
                        "type": "string",
                        "description": (
                            "Optional ISO-639 language code (e.g. 'zh', 'en'; alias/"
                            "case tolerant: 'zh_CN', '中文', 'en-US' all match). When "
                            "set, only entries whose detected language matches are "
                            "included, so the report never mixes languages (issue #309)."
                        ),
                        "default": "",
                    },
                    "persist": {
                        "type": "boolean",
                        "description": "When true, write the generated artifact to outputs/<domain>/ and return its persisted_path in the envelope (default: false).",
                        "default": False,
                    },
                },
                "required": ["domains"],
            },
        ),
        Tool(
            name="generate_tutorial",
            description=(
                "Create a step-by-step tutorial teaching a topic for a "
                "domain, with learning goals and hands-on steps. "
                "Default markdown; also agent (JSON-LD). topic filters the "
                "content; custom_instructions shape the teaching style."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional topic filter",
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format: 'markdown' (default), 'agent' (JSON-LD for LLM re-consumption)",
                        "default": "markdown",
                        "enum": ["markdown", "agent"],
                    },
                    "custom_instructions": {
                        "type": "string",
                        "description": "Optional custom instructions to tailor the output content",
                        "default": "",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user ID for preference-based personalization. When provided, stored content_preference (raw_only / processed_only / both) is auto-loaded and KB entries are tier-filtered accordingly.",
                        "default": "",
                    },
                    "persist": {
                        "type": "boolean",
                        "description": "When true, write the generated artifact to outputs/<domain>/ and return its persisted_path in the envelope (default: false).",
                        "default": False,
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="generate_presentation",
            description=(
                "Build a slide deck for a topic within a domain (slides 3-30). "
                "Outputs markdown (Reveal.js flavored), standalone html, "
                "mkslides build, or agent (JSON-LD). Pass custom_instructions "
                "for visual narrative and pacing."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Presentation topic",
                    },
                    "slides": {
                        "type": "integer",
                        "description": "Desired number of slides (3-30)",
                        "default": 10,
                    },
                    "format": {
                        "type": "string",
                        "description": (
                            "Output format: 'markdown' (default, Reveal.js-flavoured "
                            "Markdown), 'html' (standalone Reveal.js HTML5 via CDN), "
                            "'mkslides' (mkslides build with HTML fallback), "
                            "or 'agent' (JSON-LD for LLM re-consumption)."
                        ),
                        "default": "markdown",
                        "enum": ["markdown", "html", "mkslides", "agent"],
                    },
                    "custom_instructions": {
                        "type": "string",
                        "description": "Optional custom instructions to tailor the output content",
                        "default": "",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional user ID for preference-based personalization. When provided, stored content_preference (raw_only / processed_only / both) is auto-loaded and KB entries are tier-filtered accordingly.",
                        "default": "",
                    },
                    "persist": {
                        "type": "boolean",
                        "description": "When true, write the generated artifact to outputs/<domain>/ and return its persisted_path in the envelope (default: false).",
                        "default": False,
                    },
                },
                "required": ["domain", "topic"],
            },
        ),
        Tool(
            name="localize_content",
            description=(
                "Translate a KB entry or raw text into a target language. "
                "Two modes: (1) pass content_id to translate a stored KB "
                "entry (stores the translation as a new file), or (2) pass "
                "content + source_lang for direct translation without storage. "
                "Preserves medical terminology, drug names, procedures, "
                "statistics, and citations. Optionally accepts a domain "
                "name to inject terminology guardrails."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content_id": {
                        "type": "string",
                        "description": (
                            "KB entry ID to translate.  The entry must exist in the KB store."
                        ),
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "Raw text to translate directly (no KB lookup). Requires source_lang."
                        ),
                    },
                    "source_lang": {
                        "type": "string",
                        "description": (
                            "Source language code (e.g. en, zh).  Required "
                            "for direct content mode; auto-detected from "
                            "the KB entry for content_id mode."
                        ),
                    },
                    "target_lang": {
                        "type": "string",
                        "description": ("Target language code (e.g. zh, fr, ja)."),
                    },
                    "domain": {
                        "type": "string",
                        "description": (
                            "Domain name (e.g. medical-research). When "
                            "provided, loads domain-specific terminology "
                            "guardrails from knowledge/<domain>/_terminology.yaml. "
                            "In content_id mode, inferred from KB entry "
                            "if not specified."
                        ),
                    },
                },
                "required": ["target_lang"],
            },
        ),
        # -- Export / Import (2) ---------------------------------------------
        Tool(
            name="export_kb",
            description=(
                "Export knowledge base entries to specified format. "
                "Supports markdown, json, sqlite, csv, pdf, graphml, rss, agent, bundle, sitemap, epub, mobi formats."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "format": {
                        "type": "string",
                        "description": (
                            "Output format: markdown, json, sqlite, csv, pdf, graphml, rss, "
                            "agent, bundle (ZIP with PDF+JSON+MD+YAML), epub, mobi"
                        ),
                        "default": "markdown",
                        "enum": [
                            "markdown",
                            "json",
                            "sqlite",
                            "csv",
                            "pdf",
                            "graphml",
                            "rss",
                            "agent",
                            "bundle",
                            "sitemap",
                            "epub",
                            "mobi",
                        ],
                    },
                    "scope": {
                        "type": "string",
                        "description": "Export scope: domain (all entries), entry (specific IDs), collection (collection-scoped)",
                        "default": "domain",
                        "enum": ["entry", "collection", "domain"],
                    },
                    "entry_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific entry IDs to export (used when scope is 'entry')",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Optional explicit output path. Auto-generated when omitted.",
                    },
                    "base_url": {
                        "type": "string",
                        "description": (
                            "Site base URL required when format is 'sitemap' "
                            "(e.g. https://your-site.example); ignored for other formats"
                        ),
                    },
                },
                "required": ["domain", "format"],
            },
        ),
        Tool(
            name="import_kb",
            description=(
                "Import entries or source suggestions into the KB. "
                "Supports 4 formats: markdown (YAML+Markdown frontmatter), "
                "json, csv, and opml. "
                "All entry imports land in 01-Raw (KB pipeline). "
                "OPML returns source suggestions only — does NOT auto-add sources."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Target domain name (e.g. medical-research)",
                    },
                    "format": {
                        "type": "string",
                        "description": "Import format: markdown (YAML+Markdown), json, csv, opml",
                        "enum": ["markdown", "json", "csv", "opml"],
                    },
                    "data": {
                        "type": "string",
                        "description": (
                            "Raw content string to import. "
                            "For markdown: YAML frontmatter (--- delimited) + Markdown body. "
                            "For json: JSON array or single object with title, source_url, content. "
                            "For csv: CSV with header row (title, source_url, content required). "
                            "For opml: OPML XML with <outline> elements."
                        ),
                    },
                },
                "required": ["domain", "format", "data"],
            },
        ),
        # -- Email (1) -------------------------------------------------------
        Tool(
            name="send_email_digest",
            description=(
                "Generate and send a digest via SMTP email. "
                "Only sends when email is enabled in config "
                "(email.enabled: true). Requires email.smtp_host, "
                "email.from_addr, and email.to_addrs to be configured."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain to generate digest for (e.g. medical-research)",
                    },
                    "period": {
                        "type": "string",
                        "description": "Digest period: daily, weekly, monthly",
                        "default": "weekly",
                        "enum": ["daily", "weekly", "monthly"],
                    },
                    "user_id": {
                        "type": "string",
                        "description": (
                            "Optional end-user ID. When provided, the digest "
                            "honors the user's stored content_preference "
                            "(e.g. raw_only / processed_only / both). "
                            "Empty by default (no preference lookup)."
                        ),
                        "default": "",
                    },
                },
                "required": ["domain"],
            },
        ),
        # -- Email Config (1) ------------------------------------------------
        Tool(
            name="email_config",
            description=(
                "View or update email SMTP configuration. "
                "Get current settings, set SMTP host/port/credentials, "
                "enable/disable email, or send a test email."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "smtp_server": {
                        "type": "string",
                        "description": "SMTP server hostname",
                        "default": "",
                    },
                    "smtp_port": {
                        "type": "integer",
                        "description": "SMTP server port",
                        "default": 0,
                    },
                    "username": {
                        "type": "string",
                        "description": "SMTP username",
                        "default": "",
                    },
                    "password": {
                        "type": "string",
                        "description": "SMTP password",
                        "default": "",
                    },
                    "enable": {
                        "type": "boolean",
                        "description": "Enable email sending",
                        "default": False,
                    },
                    "disable": {
                        "type": "boolean",
                        "description": "Disable email sending",
                        "default": False,
                    },
                    "test": {
                        "type": "boolean",
                        "description": "Send a test email using current config",
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        # -- Custom Extraction (2) -------------------------------------------
        Tool(
            name="extract_fields",
            description=(
                "On-demand re-extraction with a custom schema. "
                "Retrieves the KB entry, runs LLM extraction with the "
                "given field names, and returns the result "
                "(does NOT persist)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content_id": {
                        "type": "string",
                        "description": "KB entry ID to re-extract",
                    },
                    "schema": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Custom field names to extract (e.g. methodology, findings)"
                        ),
                    },
                },
                "required": ["content_id", "schema"],
            },
        ),
        Tool(
            name="get_extraction",
            description=(
                "Return the extracted fields stored for a KB entry. "
                "Reads the Markdown frontmatter to retrieve "
                "``extracted_fields``."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content_id": {
                        "type": "string",
                        "description": "KB entry ID",
                    },
                },
                "required": ["content_id"],
            },
        ),
    ]
