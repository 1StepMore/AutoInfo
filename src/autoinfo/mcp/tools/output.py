"""MCP tool schemas — Output, export/import, email, custom extraction (13 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from mcp.types import Tool

from autoinfo.mcp import context as mcp_context
from autoinfo.mcp.errors import ErrorCode, error_response, success_response


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


def _handle_list_output_templates(domain: str = "", user_id: str | None = None) -> dict[str, Any]:
    """List available output templates for a domain, optionally filtered by user tier.

    When *user_id* is provided, templates are filtered so that only those
    whose ``access_level`` is accessible to the user are returned.
    When *user_id* is ``None``, all templates are returned (backward compatible).
    """
    from autoinfo.billing import check_access
    from autoinfo.output import list_output_templates as _list_output_templates

    result = _list_output_templates(domain=domain)
    templates: list[dict[str, Any]] = result["templates"]

    if user_id is not None:
        filtered: list[dict[str, Any]] = []
        for t in templates:
            access = check_access(user_id, t["access_level"])
            if access["allowed"]:
                filtered.append(t)
        result["templates"] = filtered
        result["count"] = len(filtered)

    return mcp_context._canonicalize(result)


def _handle_generate_digest(
    domain: str,
    period: str = "weekly",
    format: str = "markdown",
    custom_instructions: str = "",
    target_audience: str = "",
    include_stale: bool = False,
    recipients: list[str] | None = None,
    user_id: str = "",
    max_items: int = 0,
    product: str = "",
    language: str = "",
    ref_limit: int | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """Generate a digest of KB entries for *domain* over the given *period*.

    Dispatches to :func:`autoinfo.output.generate_digest`.
    """
    from datetime import date, timedelta

    from autoinfo.kb import KBStore
    from autoinfo.output import generate_digest as _generate_digest
    from autoinfo.output.free_tier import FreeTierLimitError

    product_template = None
    if product:
        from autoinfo.output import PRODUCT_TEMPLATES

        _product_row = next(
            (row for row in PRODUCT_TEMPLATES if row["name"] == product),
            None,
        )
        if _product_row is None:
            _valid = ", ".join(sorted(row["name"] for row in PRODUCT_TEMPLATES))
            return error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Unknown product '{product}'. Valid products: {_valid}",
                actionable=True,
            )
        product_template = _product_row["template"]

    _period_days = {"daily": 1, "weekly": 7, "monthly": 30}
    _days = _period_days.get(period, 7)
    _date_from = (date.today() - timedelta(days=_days)).isoformat()
    _store = KBStore()
    _preview = _store.list_entries(domain=domain, date_from=_date_from, limit=1)
    if not _preview:
        # generate_digest relaxes the date filter to the full domain set when
        # no entries fall in the window (data-staleness fallback).  Match that
        # so the preview gate never suppresses content the generator would
        # produce (issue #10).
        _preview = _store.list_entries(domain=domain, limit=1)
    if not _preview:
        return success_response(
            {
                "domain": domain,
                "format": format,
                "period": period,
                "status": "noop",
                "content": "",
                "message": f"No entries found for domain '{domain}' in the requested period. Run collect_sources() + process_collection() first.",
            }
        )

    try:
        result = _generate_digest(
            domain=domain,
            period=period,
            format=format,
            custom_instructions=custom_instructions,
            target_audience=target_audience,
            include_stale=include_stale,
            recipients=recipients,
            user_id=user_id,
            max_items=max_items,
            product_template=product_template,
            language=language,
            ref_limit=ref_limit,
        )
        if format in ("json", "agent"):
            # Parse JSON string back to dict for structured MCP response
            import json as _json

            _parsed = _json.loads(mcp_context._output_text(result))
            return mcp_context._maybe_persist_output(
                {"success": True, "format": format, "content": _parsed},
                persist,
                domain,
                "digest",
                format,
                _parsed,
            )
        if format == "audio":
            return mcp_context._maybe_persist_output(
                {
                    "success": True,
                    "format": "audio",
                    "content_type": "audio/mp3",
                    "encoding": "base64",
                    "content": result,
                },
                persist,
                domain,
                "digest",
                "audio",
                result,
            )
        if format == "video":
            # _render_video_scaffold returns a JSON status blob with video_path.
            import json as _json2

            try:
                parsed = _json2.loads(mcp_context._output_text(result))
            except (ValueError, TypeError):
                parsed = {"status": "ok", "video_path": result}
            return mcp_context._maybe_persist_output(
                {"success": True, "format": "video", **parsed},
                persist,
                domain,
                "digest",
                "video",
                result,
            )
        if format in ("epub", "audiobook"):
            return mcp_context._maybe_persist_output(
                {
                    "success": True,
                    "format": format,
                    "content_type": ("application/epub+zip" if format == "epub" else "audio/mpeg"),
                    "encoding": "base64",
                    "content": result,
                },
                persist,
                domain,
                "digest",
                format,
                result,
            )
        return mcp_context._maybe_persist_output(
            {"success": True, "format": format, "content": result},
            persist,
            domain,
            "digest",
            format,
            result,
        )
    except FreeTierLimitError as exc:
        # Named free-tier user over quota — unified FREE_TIER_LIMIT envelope.
        error_detail = exc.to_envelope()["error"]
        return error_response(
            code=error_detail["code"],
            message=error_detail["message"],
            actionable=error_detail["actionable"],
        )
    except ValueError as exc:
        return mcp_context._error_from_exc(
            exc, "Digest generation failed", code=ErrorCode.VALIDATION_ERROR
        )
    except Exception as exc:
        mcp_context.logger.exception("Digest generation failed for domain '%s'", domain)
        return mcp_context._error_from_exc(exc, "Digest generation failed")


def _handle_generate_report(
    domain: str,
    format: str = "markdown",
    period: str = "monthly",
    custom_instructions: str = "",
    target_audience: str = "",
    user_id: str = "",
    report_type: str = "standard",
    product: str = "",
    language: str = "",
    ref_limit: int | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """Generate a structured report for *domain* over the given *period*.

    Dispatches to :func:`autoinfo.output.generate_report`.
    """
    from datetime import date, timedelta

    from autoinfo.kb import KBStore
    from autoinfo.output import generate_report as _generate_report
    from autoinfo.output import is_no_data_product as _is_no_data_product
    from autoinfo.output.free_tier import FreeTierLimitError

    product_template = None
    if product:
        from autoinfo.output import PRODUCT_TEMPLATES

        _product_row = next(
            (row for row in PRODUCT_TEMPLATES if row["name"] == product),
            None,
        )
        if _product_row is None:
            _valid = ", ".join(sorted(row["name"] for row in PRODUCT_TEMPLATES))
            return error_response(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Unknown product '{product}'. Valid products: {_valid}",
                actionable=True,
            )
        product_template = _product_row["template"]
    elif report_type == "column":
        from autoinfo.output import PRODUCT_TEMPLATES

        product_template = next(
            (row["template"] for row in PRODUCT_TEMPLATES if row["name"] == "column"),
            None,
        )
    _period_days = {"daily": 1, "weekly": 7, "monthly": 30}
    _days = _period_days.get(period, 7)
    _date_from = (date.today() - timedelta(days=_days)).isoformat()
    _store = KBStore()
    _preview = _store.list_entries(domain=domain, date_from=_date_from, limit=1)
    if not _preview:
        # generate_report relaxes the date filter to the full domain set when
        # no entries fall in the window.  Match that so the preview gate never
        # suppresses content the generator would produce (issue #10).
        _preview = _store.list_entries(domain=domain, limit=1)
    if not _preview:
        return success_response(
            {
                "domain": domain,
                "format": format,
                "period": period,
                "status": "noop",
                "content": "",
                "message": f"No entries found for domain '{domain}' in the requested period. Run collect_sources() + process_collection() first.",
            }
        )

    try:
        # Persist under the spec product name so matrix evidence resolves
        # (column was persisted as report-markdown-* and never counted for
        # the column:markdown cell — issue #229).
        _persist_product = "column" if report_type == "column" else "report"
        result = _generate_report(
            domain=domain,
            format=format,
            period=period,
            custom_instructions=custom_instructions,
            target_audience=target_audience,
            user_id=user_id,
            report_type=report_type,
            product_template=product_template,
            language=language,
            ref_limit=ref_limit,
        )
        if _is_no_data_product(result, format):
            return success_response(
                {
                    "domain": domain,
                    "format": format,
                    "period": period,
                    "status": "noop",
                    "content": "",
                    "message": (
                        f"No curated entries for domain '{domain}' produced a "
                        "deliverable report; nothing was written. Run "
                        "collect_sources() + process_collection() first."
                    ),
                }
            )
        if format in ("json", "agent"):
            import json as _json

            parsed = _json.loads(mcp_context._output_text(result))
            return mcp_context._maybe_persist_output(
                {
                    "success": True,
                    "domain": domain,
                    "format": format,
                    "period": period,
                    "content": parsed,
                },
                persist,
                domain,
                _persist_product,
                format,
                parsed,
            )
        if format == "audio":
            return mcp_context._maybe_persist_output(
                {
                    "success": True,
                    "domain": domain,
                    "format": "audio",
                    "period": period,
                    "content_type": "audio/mp3",
                    "encoding": "base64",
                    "content": result,
                },
                persist,
                domain,
                _persist_product,
                "audio",
                result,
            )
        if format == "video":
            import json as _json3

            try:
                parsed = _json3.loads(mcp_context._output_text(result))
            except (ValueError, TypeError):
                parsed = {"status": "ok", "video_path": result}
            content = result
            if isinstance(result, str) and os.path.isfile(result):
                # generate_video returns an MP4 file path; persist expects
                # the same base64 payload shape as audio (#254).
                content = base64.b64encode(Path(result).read_bytes()).decode("ascii")
                parsed.setdefault("encoding", "base64")
            return mcp_context._maybe_persist_output(
                {
                    "success": True,
                    "domain": domain,
                    "format": "video",
                    "period": period,
                    **parsed,
                },
                persist,
                domain,
                _persist_product,
                "video",
                content,
            )
        if format in ("epub", "audiobook"):
            return mcp_context._maybe_persist_output(
                {
                    "success": True,
                    "domain": domain,
                    "format": format,
                    "period": period,
                    "content_type": ("application/epub+zip" if format == "epub" else "audio/mpeg"),
                    "encoding": "base64",
                    "content": result,
                },
                persist,
                domain,
                _persist_product,
                format,
                result,
            )
        return mcp_context._maybe_persist_output(
            {
                "success": True,
                "domain": domain,
                "format": format,
                "period": period,
                "content": result,
            },
            persist,
            domain,
            _persist_product,
            format,
            result,
        )
    except FreeTierLimitError as exc:
        error_detail = exc.to_envelope()["error"]
        return error_response(
            code=error_detail["code"],
            message=error_detail["message"],
            actionable=error_detail["actionable"],
        )
    except ValueError as exc:
        return mcp_context._error_from_exc(
            exc, "Report generation failed", code=ErrorCode.VALIDATION_ERROR
        )
    except Exception as exc:
        mcp_context.logger.exception("Report generation failed for domain '%s'", domain)
        return mcp_context._error_from_exc(exc, "Report generation failed")


def _handle_generate_cross_domain_report(
    domains: list[str],
    format: str = "markdown",
    period: str = "monthly",
    target_audience: str = "",
    report_type: str = "standard",
    user_id: str = "",
    language: str = "",
    persist: bool = False,
) -> dict[str, Any]:
    """Generate a synthesis report across multiple domains.

    Delegates to :func:`autoinfo.output.generate_report` with the
    ``domains`` parameter, using the first domain as primary for
    backward-compatible metadata.

    Parameters
    ----------
    user_id:
        Optional end-user ID forwarded to ``generate_report`` so the
        user's stored ``content_preference`` is honored.  Empty by
        default (no preference lookup).
    """
    from autoinfo.output import generate_report as _generate_report
    from autoinfo.output.free_tier import FreeTierLimitError

    # Validate at least 2 domains
    if not isinstance(domains, list) or len(domains) < 2:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message="At least 2 domains are required for cross-domain report generation. Provide a list of two or more active domain names.",
            actionable=True,
        )

    # Validate all domains exist
    try:
        config = mcp_context._load_config()
    except FileNotFoundError:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message="No project configuration found.  Run `init_project` first to set up at least one domain. See docs/dev/director-user-guide.md for setup instructions.",
            actionable=True,
        )
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Cross-domain report generation failed")
    valid_names = {d.name for d in config.domains}
    invalid = [d for d in domains if d not in valid_names]
    if invalid:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"Unknown domain(s): {', '.join(invalid)}. Valid domains: {', '.join(sorted(valid_names))}",
            actionable=True,
        )

    try:
        result = _generate_report(
            domain=domains[0],
            domains=domains,
            format=format,
            period=period,
            target_audience=target_audience,
            report_type=report_type,
            user_id=user_id,
            language=language,
        )
        if format in ("json", "agent"):
            import json as _json

            parsed = _json.loads(mcp_context._output_text(result))
            return mcp_context._maybe_persist_output(
                {
                    "success": True,
                    "domain": domains[0],
                    "domains": domains,
                    "format": format,
                    "period": period,
                    "content": parsed,
                },
                persist,
                domains[0],
                "report",
                format,
                parsed,
            )
        if format == "audio":
            return mcp_context._maybe_persist_output(
                {
                    "success": True,
                    "domain": domains[0],
                    "domains": domains,
                    "format": "audio",
                    "period": period,
                    "content_type": "audio/mp3",
                    "encoding": "base64",
                    "content": result,
                },
                persist,
                domains[0],
                "report",
                "audio",
                result,
            )
        if format == "video":
            import json as _json4

            try:
                parsed = _json4.loads(mcp_context._output_text(result))
            except (ValueError, TypeError):
                parsed = {"status": "ok", "video_path": result}
            return mcp_context._maybe_persist_output(
                {
                    "success": True,
                    "domain": domains[0],
                    "domains": domains,
                    "format": "video",
                    "period": period,
                    **parsed,
                },
                persist,
                domains[0],
                "report",
                "video",
                result,
            )
        if format in ("epub", "audiobook"):
            return mcp_context._maybe_persist_output(
                {
                    "success": True,
                    "domain": domains[0],
                    "domains": domains,
                    "format": format,
                    "period": period,
                    "content_type": ("application/epub+zip" if format == "epub" else "audio/mpeg"),
                    "encoding": "base64",
                    "content": result,
                },
                persist,
                domains[0],
                "report",
                format,
                result,
            )
        return mcp_context._maybe_persist_output(
            {
                "success": True,
                "domain": domains[0],
                "domains": domains,
                "format": format,
                "period": period,
                "content": result,
            },
            persist,
            domains[0],
            "report",
            format,
            result,
        )
    except FreeTierLimitError as exc:
        error_detail = exc.to_envelope()["error"]
        return error_response(
            code=error_detail["code"],
            message=error_detail["message"],
            actionable=error_detail["actionable"],
        )
    except ValueError as exc:
        return mcp_context._error_from_exc(
            exc, "Cross-domain report generation failed", code=ErrorCode.VALIDATION_ERROR
        )
    except Exception as exc:
        mcp_context.logger.exception(
            "Cross-domain report generation failed for domains %s",
            domains,
        )
        return mcp_context._error_from_exc(exc, "Cross-domain report generation failed")


def _handle_generate_tutorial(
    domain: str,
    topic: str | None = None,
    format: str = "markdown",
    custom_instructions: str = "",
    user_id: str = "",
    persist: bool = False,
) -> dict[str, Any]:
    """Generate a structured tutorial for *domain*.

    Thin wrapper around :func:`autoinfo.output.generate_tutorial`.

    Parameters
    ----------
    user_id:
        Optional end-user ID forwarded to ``generate_tutorial`` so the
        user's stored ``content_preference`` is honored.  Empty by
        default (no preference lookup).
    """
    from autoinfo.output import generate_tutorial as _generate_tutorial

    try:
        result = _generate_tutorial(
            domain=domain, format=format, custom_instructions=custom_instructions, user_id=user_id
        )
        if format == "agent":
            import json as _json

            return mcp_context._maybe_persist_output(
                {
                    "success": True,
                    "format": format,
                    "domain": domain,
                    "topic": topic,
                    "content": _json.loads(mcp_context._output_text(result)),
                },
                persist,
                domain,
                "tutorial",
                format,
                _json.loads(mcp_context._output_text(result)),
            )
        return mcp_context._maybe_persist_output(
            {
                "success": True,
                "format": format,
                "domain": domain,
                "topic": topic,
                "content": result,
            },
            persist,
            domain,
            "tutorial",
            format,
            result,
        )
    except ValueError as exc:
        return mcp_context._error_from_exc(
            exc, "Tutorial generation failed", code=ErrorCode.VALIDATION_ERROR
        )
    except Exception as exc:
        mcp_context.logger.exception("Tutorial generation failed for domain '%s'", domain)
        return mcp_context._error_from_exc(exc, "Tutorial generation failed")


def _handle_generate_presentation(
    domain: str,
    topic: str | None = None,
    slides: int = 10,
    format: str = "markdown",
    custom_instructions: str = "",
    user_id: str = "",
    persist: bool = False,
) -> dict[str, Any]:
    """Generate a slide-based presentation for *topic* within *domain*.

    Thin wrapper around :func:`autoinfo.output.generate_presentation`.

    Parameters
    ----------
    user_id:
        Optional end-user ID forwarded to ``generate_presentation`` so
        the user's stored ``content_preference`` is honored.  Empty by
        default (no preference lookup).
    """
    from autoinfo.output import generate_presentation as _generate_presentation

    try:
        topic_str = topic or ""
        result = _generate_presentation(
            domain=domain,
            topic=topic_str,
            slide_count=slides,
            format=format,
            custom_instructions=custom_instructions,
            user_id=user_id,
        )
        if format == "agent":
            import json as _json

            return mcp_context._maybe_persist_output(
                {
                    "success": True,
                    "domain": domain,
                    "topic": topic,
                    "slides": slides,
                    "format": format,
                    "content": _json.loads(mcp_context._output_text(result)),
                },
                persist,
                domain,
                "presentation",
                format,
                _json.loads(mcp_context._output_text(result)),
            )
        return mcp_context._maybe_persist_output(
            {
                "success": True,
                "domain": domain,
                "topic": topic,
                "slides": slides,
                "format": format,
                "content": result,
            },
            persist,
            domain,
            "presentation",
            format,
            result,
        )
    except ValueError as exc:
        return mcp_context._error_from_exc(
            exc,
            "Presentation generation failed",
            code=ErrorCode.VALIDATION_ERROR,
        )
    except Exception as exc:
        mcp_context.logger.exception("Presentation generation failed for domain '%s'", domain)
        return mcp_context._error_from_exc(exc, "Presentation generation failed")


def _handle_localize_content(**kwargs: Any) -> dict[str, Any]:
    """Translate a KB entry or raw text via LLM.

    Dispatches to :func:`autoinfo.output.localize_content`.
    Supports both content_id mode (reads from KB, stores translation)
    and direct content mode (returns translated text only).

    Parameters match :func:`autoinfo.output.localize_content`.
    """
    from autoinfo.output import localize_content as _localize

    try:
        result = _localize(**kwargs)
        return mcp_context._canonicalize(result)
    except ValueError as exc:
        return mcp_context._error_from_exc(
            exc, "Localization failed", code=ErrorCode.VALIDATION_ERROR
        )
    except Exception as exc:
        mcp_context.logger.exception("Localization failed")
        return mcp_context._error_from_exc(exc, "Localization failed")


def _handle_export_kb(
    domain: str,
    format: str = "markdown",
    scope: str = "domain",
    entry_ids: list[str] | None = None,
    output_path: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Export knowledge base entries to specified format.

    Dispatches to :func:`autoinfo.output.export_kb`.

    Parameters
    ----------
    domain:
        Domain name (e.g. medical-research).
    format:
        Output format: ``"markdown"``, ``"json"``, ``"sqlite"``, ``"csv"``,
        ``"pdf"``, or ``"graphml"``.  Defaults to ``"markdown"``.
    scope:
        Export scope: ``"domain"`` (all entries in domain), ``"entry"``
        (specific entries by ID), or ``"collection"`` (collection-scoped).
        Defaults to ``"domain"``.
    entry_ids:
        Specific entry IDs to export (used when scope == ``"entry"``).
    output_path:
        Optional explicit output path.  When omitted, the file is written
        to the ``exports/`` directory with an auto-generated name.
    base_url:
        Site base URL required when ``format`` is ``"sitemap"`` (e.g.
        ``"https://your-site.example"``).  Ignored for other formats.

    Returns
    -------
    dict
        ``{format, path, entries_count, file_size_bytes, domain, success}``.
    """
    from autoinfo.output import export_kb as _export_kb

    try:
        collection_id: str | None = None
        if scope == "entry" and entry_ids:
            collection_id = entry_ids[0]
        elif scope == "collection":
            collection_id = "__all__"

        result = _export_kb(
            domain=domain,
            format=format,
            collection_id=collection_id,
            base_url=base_url,
        )

        file_path = result.get("path", "")
        if file_path and os.path.isfile(file_path):
            result["file_size_bytes"] = os.path.getsize(file_path)
        else:
            result["file_size_bytes"] = 0

        return mcp_context._canonicalize(result)
    except ValueError as exc:
        return mcp_context._error_from_exc(exc, "Export KB failed", code=ErrorCode.VALIDATION_ERROR)
    except Exception as exc:
        mcp_context.logger.exception("Export KB failed for domain '%s'", domain)
        return mcp_context._error_from_exc(exc, "Export KB failed")


def _handle_import_kb(
    domain: str,
    format: str,
    data: str,
) -> dict[str, Any]:
    """Import entries or source suggestions into the KB.

    Dispatches to the appropriate handler in :mod:`autoinfo.importer`
    based on *format*.

    Parameters
    ----------
    domain:
        Target domain name (e.g. medical-research).
    format:
        Import format: ``"markdown"``, ``"json"``, ``"csv"``, or ``"opml"``.
    data:
        Raw content string to import (YAML+Markdown, JSON, CSV, or OPML XML).

    Returns
    -------
    dict
        For ``markdown`` / ``json`` / ``csv``::
            ``{domain, format, entries_imported, entries_failed, errors}``
        For ``opml``::
            ``{type: "source_list", suggestions, action_required, domain, format}``
    """
    from autoinfo.importer import import_kb as _import_kb

    try:
        result = _import_kb(domain=domain, format=format, data=data)
        return mcp_context._canonicalize(result)
    except ValueError as exc:
        return mcp_context._error_from_exc(exc, "Import KB failed", code=ErrorCode.VALIDATION_ERROR)
    except Exception as exc:
        mcp_context.logger.exception("Import KB failed for domain '%s'", domain)
        return mcp_context._error_from_exc(exc, "Import KB failed")


def _handle_send_email_digest(
    domain: str,
    period: str = "weekly",
    user_id: str = "",
) -> dict[str, Any]:
    """Generate and send a digest via SMTP email.

    Dispatches to :func:`autoinfo.email_sender.send_digest`.
    Only sends when ``config.email.enabled == True``.

    Parameters
    ----------
    domain:
        Domain to generate the digest for.
    period:
        Digest period: ``"daily"``, ``"weekly"``, ``"monthly"``.
        Defaults to ``"weekly"``.
    user_id:
        Optional end-user ID forwarded to the email sender so the
        user's stored ``content_preference`` is honored.  Empty by
        default (no preference lookup).

    Returns
    -------
    dict
        ``{success, message, recipients, domain, period}``.
    """
    from autoinfo.email_sender import send_digest as _send_email

    try:
        config = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    if not config.email.enabled:
        return error_response(
            code=ErrorCode.EMAIL_NOT_ENABLED,
            message=(
                "Email delivery is not enabled. "
                "Set 'email.enabled: true' in .autoinfo/config.yaml "
                "and configure email.smtp_host, email.from_addr, "
                "and email.to_addrs."
            ),
            actionable=True,
        )

    try:
        result = _send_email(domain=domain, period=period, config=config, user_id=user_id)
        return mcp_context._canonicalize(result)
    except RuntimeError as exc:
        return mcp_context._error_from_exc(
            exc, "Email digest send failed", code=ErrorCode.EMAIL_SEND_FAILED
        )
    except Exception as exc:
        mcp_context.logger.exception("Email digest send failed for domain '%s'", domain)
        return mcp_context._error_from_exc(exc, "Email digest send failed")


def _handle_email_config(
    smtp_server: str = "",
    smtp_port: int = 0,
    username: str = "",
    password: str = "",
    enable: bool = False,
    disable: bool = False,
    test: bool = False,
) -> dict[str, Any]:
    """View or update email SMTP configuration.

    Parameters
    ----------
    smtp_server:
        SMTP server hostname.
    smtp_port:
        SMTP server port.
    username:
        SMTP username.
    password:
        SMTP password.
    enable:
        Enable email sending.
    disable:
        Disable email sending.
    test:
        Send a test email using current config.

    Returns
    -------
    dict
        ``{config: {smtp_host, smtp_port, enabled, ...}, updated, test_result}``.
    """
    import smtplib
    from email.mime.text import MIMEText

    try:
        cfg = mcp_context._load_config()
    except Exception as exc:
        return mcp_context._error_from_exc(exc, "Failed to load the project configuration")

    email_cfg = cfg.email

    if enable and disable:
        return error_response(
            code=ErrorCode.VALIDATION_ERROR,
            message="Cannot use both enable and disable.",
            actionable=True,
        )

    changed = False
    if smtp_server:
        email_cfg.smtp_host = smtp_server
        changed = True
    if smtp_port > 0:
        email_cfg.smtp_port = smtp_port
        changed = True
    if username:
        email_cfg.smtp_user = username
        changed = True
    if password:
        email_cfg.smtp_pass = password
        changed = True
    if enable:
        email_cfg.enabled = True
        changed = True
    if disable:
        email_cfg.enabled = False
        changed = True

    if changed:
        mcp_context._save_config(cfg)

    config_summary: dict[str, Any] = {
        "smtp_host": email_cfg.smtp_host or "(not set)",
        "smtp_port": email_cfg.smtp_port,
        "smtp_user": email_cfg.smtp_user or "(not set)",
        "smtp_pass": "****" if email_cfg.smtp_pass else "(not set)",
        "from_addr": email_cfg.from_addr or "(not set)",
        "to_addrs": email_cfg.to_addrs or [],
        "enabled": email_cfg.enabled,
    }

    response: dict[str, Any] = {
        "config": config_summary,
        "updated": changed,
        "test_result": None,
    }

    if test:
        if not email_cfg.smtp_host:
            response["test_result"] = "skipped: SMTP server not configured"
        elif not email_cfg.from_addr and not email_cfg.smtp_user:
            response["test_result"] = "skipped: no from address configured"
        elif not email_cfg.to_addrs:
            response["test_result"] = "skipped: no recipients configured"
        else:
            from_addr = email_cfg.from_addr or email_cfg.smtp_user
            to_addrs = email_cfg.to_addrs

            msg = MIMEText(
                "This is a test email from AutoInfo.\n\n"
                "If you received this, SMTP configuration is working correctly."
            )
            msg["Subject"] = "[AutoInfo] Test Email"
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_addrs)

            server = None
            try:
                server = smtplib.SMTP(email_cfg.smtp_host, email_cfg.smtp_port, timeout=30)
                server.ehlo()
                if server.has_extn("STARTTLS"):
                    server.starttls()
                    server.ehlo()
                if email_cfg.smtp_user and email_cfg.smtp_pass:
                    server.login(email_cfg.smtp_user, email_cfg.smtp_pass)
                server.sendmail(from_addr, to_addrs, msg.as_string())
                response["test_result"] = f"success: sent to {', '.join(to_addrs)}"
            except (smtplib.SMTPException, OSError) as exc:
                response["test_result"] = f"failed: {exc}"
            finally:
                if server is not None:
                    try:
                        server.quit()
                    except Exception:
                        pass

    return mcp_context._canonicalize(response)


def _handle_extract_fields(content_id: str, schema: list[str]) -> dict[str, Any]:
    """On-demand re-extraction with custom schema.

    Retrieves the KB entry for *content_id*, reconstructs an :class:`Item`
    from its stored content, and runs LLM extraction with the given *schema*.
    This does **not** persist the result — it is a one-off re-extraction.
    """
    from autoinfo.kb import KBStore
    from autoinfo.llm import LLMExtractor
    from autoinfo.models import Item

    store = KBStore()
    entry = store.get_entry(content_id)
    if entry is None:
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"Entry '{content_id}' not found",
            actionable=True,
        )

    # Reconstruct a minimal Item from the KB entry's stored content
    item = Item(
        id=content_id,
        source_name=entry.get("source_platform", ""),
        source_type=entry.get("source_type", ""),
        source_url=entry.get("source_url", ""),
        title=entry.get("title", ""),
        content=entry.get("content", ""),
        collected_at=entry.get("collected_at", ""),
        domain=entry.get("domain", ""),
    )

    extractor = LLMExtractor()
    result = extractor.extract(item, schema=schema)

    return {
        "content_id": content_id,
        "tl_dr": result.tl_dr,
        "key_points": result.key_points,
        "entities": result.entities,
        "relevance_score": result.relevance_score,
        "custom_fields": result.custom_fields,
    }


def _handle_get_extraction(content_id: str) -> dict[str, Any]:
    """Return what was extracted for a KB entry.

    Reads the Markdown frontmatter to retrieve ``extracted_fields`` (populated
    when custom extraction fields were used during processing).
    """
    from autoinfo.kb import KBStore

    store = KBStore()
    entry = store.get_entry(content_id)
    if entry is None:
        return error_response(
            code=ErrorCode.NOT_FOUND,
            message=f"Entry '{content_id}' not found",
            actionable=True,
        )

    # Parse the Markdown frontmatter for extracted_fields
    file_path = entry.get("file_path", "")
    extracted_fields: dict[str, Any] = {}
    if file_path:
        fp = Path(file_path)
        if fp.is_file():
            raw = fp.read_text(encoding="utf-8")
            if raw.startswith("---"):
                end_idx = raw.find("---", 3)
                if end_idx != -1:
                    fm_raw = raw[3:end_idx]
                    import yaml  # noqa: PLC0415 — deferred import

                    fm = yaml.safe_load(fm_raw) or {}
                    extracted_fields = fm.get("extracted_fields", {})

    return {
        "content_id": content_id,
        "title": entry.get("title", ""),
        "summary": entry.get("summary", ""),
        "relevance_score": entry.get("relevance_score", 0),
        "dedup_status": entry.get("dedup_status", "unknown"),
        "quality_tier": entry.get("quality_tier", 1),
        "extracted_fields": extracted_fields,
    }
