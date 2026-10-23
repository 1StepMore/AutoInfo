"""MCP tool schemas — Sources, topics, keywords, collection (19 tools).

Phase 1 of #581: schemas extracted from ``mcp/server.py::_full_tool_list``
verbatim.  ``build_tools()`` returns FRESH ``Tool`` objects on every call,
so ``_decorate_tools`` mutation never leaks across calls.
"""

from __future__ import annotations

from mcp.types import Tool


def build_tools() -> list[Tool]:
    """Return the 19 schemas for this module, in registration order."""
    return [
        # -- Source Management (5) -------------------------------------------
        Tool(
            name="add_source",
            description=(
                "Add a data source (idempotent — dedup by url + type + domain). "
                "Supports 6 source types: api, rss, web, webhook, email, pdf. "
                "For email sources, pass imap_server/imap_port/imap_username/"
                "imap_password/imap_mailbox convenience params. "
                "For webhook sources, pass webhook_secret for HMAC verification. "
                "All types accept an optional settings dict for arbitrary configuration."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Human-readable source name",
                    },
                    "url": {
                        "type": "string",
                        "description": "Source URL. email: imap(s)://host, pdf: file://path or http(s)://url, others: http(s)://url",
                    },
                    "type": {
                        "type": "string",
                        "description": "Source type (api, rss, web, webhook, email, pdf)",
                        "default": "api",
                        "enum": [
                            "api",
                            "rss",
                            "web",
                            "webhook",
                            "email",
                            "pdf",
                            "akshare",
                            "sec_edgar",
                            "edx_sitemap",
                        ],
                    },
                    "domain": {
                        "type": "string",
                        "description": "Domain to add this source to",
                    },
                    "settings": {
                        "type": "object",
                        "description": "Optional key-value configuration (stored in SourceConfig.settings)",
                    },
                    "requires_key": {
                        "type": "boolean",
                        "description": (
                            "Whether this source requires an API key/credential. "
                            "Defaults to derived from the source type (true for "
                            "known key-requiring types, e.g. nyt, ap_api, "
                            "reuters_mcp, unpaywall, youtube)."
                        ),
                    },
                    "imap_server": {
                        "type": "string",
                        "description": "Email type only: IMAP server hostname (e.g. imap.gmail.com)",
                    },
                    "imap_port": {
                        "type": "integer",
                        "description": "Email type only: IMAP port (default 993)",
                    },
                    "imap_username": {
                        "type": "string",
                        "description": "Email type only: IMAP username",
                    },
                    "imap_password": {
                        "type": "string",
                        "description": "Email type only: IMAP password (or set AUTOINFO_EMAIL_PASSWORD env var)",
                    },
                    "imap_mailbox": {
                        "type": "string",
                        "description": "Email type only: IMAP mailbox name (default INBOX)",
                    },
                    "webhook_secret": {
                        "type": "string",
                        "description": "Webhook type only: HMAC shared secret for payload verification",
                    },
                },
                "required": ["name", "url", "domain"],
            },
        ),
        Tool(
            name="add_sources",
            description="Batch-add sources with per-source error isolation. Each source object supports the same parameters as add_source.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Human-readable source name",
                                },
                                "url": {
                                    "type": "string",
                                    "description": "Source URL. email: imap(s)://host, pdf: file://path or http(s)://url, others: http(s)://url",
                                },
                                "type": {
                                    "type": "string",
                                    "default": "api",
                                    "description": "Source type (api, rss, web, webhook, email, pdf)",
                                    "enum": [
                                        "api",
                                        "rss",
                                        "web",
                                        "webhook",
                                        "email",
                                        "pdf",
                                        "akshare",
                                        "sec_edgar",
                                        "edx_sitemap",
                                    ],
                                },
                                "domain": {
                                    "type": "string",
                                    "description": "Domain to add this source to",
                                },
                                "settings": {
                                    "type": "object",
                                    "description": "Optional key-value configuration (stored in SourceConfig.settings)",
                                },
                                "requires_key": {
                                    "type": "boolean",
                                    "description": (
                                        "Whether this source requires an API key/credential. "
                                        "Defaults to derived from the source type (true for "
                                        "known key-requiring types, e.g. nyt, ap_api, "
                                        "reuters_mcp, unpaywall, youtube)."
                                    ),
                                },
                                "imap_server": {
                                    "type": "string",
                                    "description": "Email type only: IMAP server hostname",
                                },
                                "imap_port": {
                                    "type": "integer",
                                    "description": "Email type only: IMAP port (default 993)",
                                },
                                "imap_username": {
                                    "type": "string",
                                    "description": "Email type only: IMAP username",
                                },
                                "imap_password": {
                                    "type": "string",
                                    "description": "Email type only: IMAP password",
                                },
                                "imap_mailbox": {
                                    "type": "string",
                                    "description": "Email type only: IMAP mailbox name (default INBOX)",
                                },
                                "webhook_secret": {
                                    "type": "string",
                                    "description": "Webhook type only: HMAC shared secret",
                                },
                            },
                            "required": ["name", "url", "domain"],
                        },
                        "description": "List of source objects to add",
                    },
                },
                "required": ["sources"],
            },
        ),
        Tool(
            name="remove_source",
            description="Remove a source by its source_id (format: 'domain:name'). Deleting a source stops future collection from it without touching already-collected items. Requires confirm=True and an explicit actor for the audit trail.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "Source identifier in 'domain:name' format (e.g. 'medical-research:pubmed'). Returned by add_source in the response.",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be True to confirm this destructive operation",
                        "default": False,
                    },
                    "actor": {
                        "type": "string",
                        "description": "Required. Actor requesting this destructive operation (must be passed explicitly)",
                    },
                },
                "required": ["source_id", "actor"],
            },
        ),
        Tool(
            name="test_source",
            description="Test whether a source URL is reachable and return metadata",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Source URL to test",
                    },
                    "type": {
                        "type": "string",
                        "description": "Source type (api, rss, web, webhook, email, pdf)",
                        "default": "api",
                        "enum": [
                            "api",
                            "rss",
                            "web",
                            "webhook",
                            "email",
                            "pdf",
                            "akshare",
                            "sec_edgar",
                            "edx_sitemap",
                        ],
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="list_sources",
            description=(
                "List all configured collection sources for a domain, with "
                "each source's id, type, and platform. Use to inspect what "
                "feeds a domain before adding or removing sources."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                },
                "required": ["domain"],
            },
        ),
        # -- Topic Management (6) --------------------------------------------
        Tool(
            name="add_topic",
            description="Add a topic to a domain (idempotent by name+domain). Topics focus collection on specific subjects; use before collect_sources so the topic's keywords drive which items get fetched. Returns the new or existing topic.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name",
                    },
                    "name": {
                        "type": "string",
                        "description": "Topic name",
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of related keywords",
                        "default": [],
                    },
                },
                "required": ["domain", "name"],
            },
        ),
        Tool(
            name="remove_topic",
            description="Remove a topic from a domain. Stops topic-scoped collection for that name; existing items stay in the KB. Use to narrow collection scope when a research interest ends.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name",
                    },
                    "topic_id": {
                        "type": "string",
                        "description": "Topic identifier — name or 'domain:name' format (e.g. 'IVF breakthroughs' or 'medical-research:IVF breakthroughs'). Returned by add_topic in the response.",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be True to confirm this destructive operation",
                        "default": False,
                    },
                    "actor": {
                        "type": "string",
                        "description": "Required. Actor requesting this destructive operation (must be passed explicitly)",
                    },
                },
                "required": ["domain", "topic_id", "actor"],
            },
        ),
        Tool(
            name="list_topics",
            description=(
                "List all tracked topics and their keywords for a domain. "
                "Topics group collected items by area; use to review "
                "coverage before collecting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="list_keywords",
            description="List keywords with topic grouping, multi-language support, and scoring info",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional topic name filter",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="topic_group_add",
            description="Assign a group to one or more topics within a domain",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "group_name": {
                        "type": "string",
                        "description": "Name of the group to assign topics to",
                    },
                    "topic_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of topic names to assign to this group",
                    },
                },
                "required": ["domain", "group_name", "topic_names"],
            },
        ),
        Tool(
            name="topic_group_remove",
            description="Remove a group assignment from all topics in that group",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "group_name": {
                        "type": "string",
                        "description": "Name of the group whose assignment should be removed from all topics",
                    },
                },
                "required": ["domain", "group_name"],
            },
        ),
        # -- Keywords Management (3) -----------------------------------------
        Tool(
            name="approve_keyword",
            description="Approve a keyword — move from auto_added to verified state",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to approve",
                    },
                },
                "required": ["domain", "keyword"],
            },
        ),
        Tool(
            name="reject_keyword",
            description="Reject a keyword — move to deprecated state. Marks the keyword so suggest_keywords and extraction no longer propose it. Use to prune noisy terms that keep appearing in collected content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to reject",
                    },
                },
                "required": ["domain", "keyword"],
            },
        ),
        Tool(
            name="suggest_keywords",
            description="Use LLM to suggest relevant keywords from a text input",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name for context",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to extract keywords from",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of suggestions (default 10)",
                        "default": 10,
                    },
                },
                "required": ["domain", "text"],
            },
        ),
        # -- Collection / Processing (5) -------------------------------------
        Tool(
            name="collect_sources",
            description=(
                "Execute a collection run for a domain. When domain is "
                "omitted, collects from ALL active domains and returns a "
                "{domains: {name: job_id, ...}, collected_count: N} mapping."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": (
                            "Domain name (e.g. medical-research). "
                            "Omit to collect from all active domains."
                        ),
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional topic / keyword filter",
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": ("Optional list of source names to restrict to"),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max items per source",
                        "default": 20,
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": ("If true, preview only — no storage"),
                        "default": False,
                    },
                    "resume_from": {
                        "type": "string",
                        "description": (
                            "Checkpoint/resume mode for a long collection run "
                            "(R-A-01): 'auto' skips sources already completed "
                            "in the checkpoint, 'start' checkpoints a fresh "
                            "run, or a source name to start at that source. "
                            "Omit for a legacy run that writes no checkpoint."
                        ),
                        "default": "",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_collection_progress",
            description="Return current collection progress for a domain (in-memory state). Reports items fetched, remaining, per-source status and an optional job_id lookup. Poll this while collect_sources runs to surface live progress to the user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Optional domain name — returns all domains if omitted",
                        "default": "",
                    },
                    "job_id": {
                        "type": "string",
                        "description": "Optional job_id to look up collection progress by job",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_collection_status",
            description="Return full collection results for a domain (last run). Summarizes the previous collect_sources execution: total items, per-source counts, failures and the run timestamp. Use after a collection finishes to inspect what was gathered.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="process_collection",
            description=(
                "Execute a processing (LLM extraction) run for a domain. "
                "Optionally runs G4 factual consistency gate (check_factual) "
                "and G5 translation accuracy gate (check_translation)."
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
                        "description": (
                            "Optional topic name whose keywords seed the G3 "
                            "relevance gate. When omitted, G3 defaults to the "
                            "union of all the domain's topic keywords."
                        ),
                    },
                    "model": {
                        "type": "string",
                        "description": (
                            "Optional LLM model override (e.g. deepseek/deepseek-chat)"
                        ),
                    },
                    "batch_size": {
                        "type": "integer",
                        "description": (
                            "Max number of items to process per run (0 = all, default 0)"
                        ),
                        "default": 0,
                    },
                    "check_factual": {
                        "type": "boolean",
                        "description": (
                            "Run G4 factual consistency gate "
                            "(LLM-based check of summary vs source). "
                            "Default: False."
                        ),
                        "default": False,
                    },
                    "check_translation": {
                        "type": "boolean",
                        "description": (
                            "Run G5 translation accuracy gate "
                            "(LLM-based check of translation vs source). "
                            "Default: False."
                        ),
                        "default": False,
                    },
                },
                "required": ["domain"],
            },
        ),
        Tool(
            name="get_processing_progress",
            description="Get processing progress for a domain or job_id. Reports items processed, pending, and per-stage gate results during process_collection. Poll this to surface live LLM extraction progress to the operator.",
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name (e.g. medical-research)",
                    },
                    "job_id": {
                        "type": "string",
                        "description": "Optional job_id to look up processing progress by job",
                    },
                },
                "required": [],
            },
        ),
    ]
