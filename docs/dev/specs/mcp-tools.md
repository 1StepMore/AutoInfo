# MCP Tool Inventory

> Extracted from `founder-expectations.md §12.11`. References: all F-numbers — every feature has a corresponding MCP tool surface.
> **Keystone matrix:** [`docs/dev/cross-dimensional-catalog.md`](../cross-dimensional-catalog.md) — MCP tools are the B2 (Direct Agent) interface to every A1-A7 pipeline capability. The CD catalog's B2 row shows which stages have full tool coverage and which have gaps.

**v1.8.0: 132 tools across 32 categories**. v1.5 added 3 categories (Quality Gate Config, Product, Alert Rules). v1.6 adds 5 categories (End User, Cost, Data Privacy, Knowledge Lifecycle, Observability). v1.6.2 adds 12 tools: `reindex_kb`, `find_similar_items`, `get_budget_thresholds`, `set_budget_thresholds`, `list_active_deliveries`, `get_delivery_log`, `get_billing_summary`, `get_enduser_history`, `get_enduser_products`, `get_enduser_usage`, `get_enduser_invoice`, `query_delivery_log`. v1.8.0 adds 12 tools + 1 new category (Audit): `get_tool_count`, `topic_group_add`, `topic_group_remove`, `clean_cache`, `create_kb_entry`, `knowledge_graph_export`, `cefr_batch`, `email_config`, `get_feeds`, `cost_dashboard`, `cost_allocation`, `query_audit_log`.

---

| Category | Tools |
|----------|-------|
| **System** | `health_check`, `diagnose_system`, `get_config`, `list_available_models`, `get_tool_count` |
| **Discovery** | `list_domains`, `list_available_platforms`, `get_domain_schema`, `get_effective_llm_config`, `list_output_templates`, `activate_domain`, `deactivate_domain`, `get_domain_config` |
| **Domain** | `add_domain`, `remove_domain` |
| **Source** | `add_source` (idempotent), `add_sources` (batch), `remove_source`, `test_source` (with extract_fields + tier warnings), `list_sources`, `get_source_health` |
| **Topic** | `add_topic`, `remove_topic`, `list_topics`, `list_keywords`, `approve_keyword`, `reject_keyword`, `suggest_keywords`, `topic_group_add`, `topic_group_remove` |
| **Collection** | `collect_sources` (with dry_run), `get_collection_progress`, `get_collection_status`, `process_collection` (with batch), `get_processing_progress`, `batch_run`, `clean_cache` |
| **KB** | `search_knowledge_base` (hybrid: FTS5+vector, paginated), `get_kb_entry`, `list_summaries`, `get_summary`, `create_kb_entry` (direct Raw-tier with source metadata), `create_kb_draft` (from Raw only), `reject_kb_draft`, `list_kb_tier`, `reindex_kb`, `flag_for_knowledge_base` |
| **KB Relations** | `link_items`, `get_item_relations` |
| **KB Versioning** | `get_entry_history`, `restore_entry_version` |
| **KB Monitor** | `get_collection_stats`, `get_collection_diff` |
| **KB Graph** | `query_knowledge_graph`, `knowledge_graph_export` |
| **Output** | `list_output_templates`, `generate_digest`, `generate_report` (Markdown/JSON/PDF/HTML), `generate_tutorial`, `generate_presentation`, `localize_content` |
| **Export/Import** | `export_kb`, `import_kb` |
| **CEFR** | `classify_cefr` (EN/ZH/JA LLM-based classification), `cefr_batch` (batch classification) |
| **Keywords** | `approve_keyword`, `reject_keyword`, `suggest_keywords` |
| **Email** | `send_email_digest`, `email_config` |
| **Q&A** | `query_collected` (FTS5 + LLM synthesis with source citations) |
| **Custom Extraction** | `extract_fields`, `get_extraction` |
| **Cron** | `list_schedules`, `add_schedule`, `remove_schedule`, `run_schedules`, `get_schedule_status` |
| **Source Health** | `get_source_health`, `rate_item`, `get_feeds` (RSS feeds, supports format="rss") |
| **Projects** | `init_project`, `list_projects`, `get_project_assets`, `archive_project` |
| **Monitor** | `list_active_collections`, `list_active_deliveries` |
| **Webhooks** | `set_domain_webhooks`, `get_domain_webhooks` |
| **Quality Gate Config** | `get_gate_config`, `set_gate_config` |
| **Product** | `list_products`, `get_product` |
| **Alert Rules** | `add_alert_rule`, `get_alert_rules`, `remove_alert_rule` |
| **End User** | `send_to_enduser`, `get_enduser_history`, `get_enduser_products`, `query_delivery_log`, `get_delivery_log`, `activate_trial`, `check_trial_expiry`, `update_preferences`, `get_preferences`, `get_subscription_status` |
| **Cost** | `get_billing_summary`, `get_budget_thresholds`, `set_budget_thresholds`, `create_checkout_session`, `get_enduser_usage`, `get_enduser_invoice`, `cost_dashboard`, `cost_allocation` |
| **Data Privacy** | `soft_delete_entry` (with purge flag), `restore_entry`, `export_user_data`, `delete_user_data` |
| **Knowledge Lifecycle** | `compare_versions`, `find_similar_items`, `merge_items`, `get_domain_decay`, `mark_stale`, `calculate_freshness_score` |
| **Observability** | `trace_item`, `get_metrics`, `get_prometheus_metrics`, `diagnose_system` |
| **Audit** | `query_audit_log` (immutable audit log query) |
| **Agent Callbacks** | `set_agent_callback`, `list_agent_callbacks`, `remove_agent_callback` |

All tools accept `domain` parameter where applicable. Pagination (`limit`/`offset`/`total_count`) on all list/search tools.
