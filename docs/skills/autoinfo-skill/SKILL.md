# AutoInfo MCP Operation Skill

Use this skill when the task involves operating, configuring, or querying
the AutoInfo information tracking platform via its MCP tools.

## Prerequisites

- AutoInfo MCP server must be running (`python -m autoinfo.mcp.server`)
- MCP tools auto-discovered via protocol — no manual config needed
- Director-user communicates intent in natural language

## Operating Model

```
Human (director) ──NL──> You ──MCP tools──> AutoInfo Server
                             │
                             ▼
                      End User (paying customer)
                         receives products via
                      delivery channels (SMTP, webhook,
                      Telegram, WeChat, DingTalk, FeiShu, Discord)
```

You are the interface. The human tells you what they want tracked, and
you translate that into AutoInfo tool calls. AutoInfo delivers finished
products (digests, reports, alerts, feeds) to End Users.

## Tool Discovery

Not sure what tools exist? Use MCP protocol discovery.
Full catalog (141 tools across **35 categories**):

| Category | Key Tools |
|----------|-----------|
| **System** | `health_check`, `diagnose_system`, `get_config`, `list_available_models`, `get_tool_count`, `configure_llm` |
| **Discovery** | `list_domains`, `list_available_platforms`, `get_domain_schema`, `get_effective_llm_config`, `list_output_templates`, `activate_domain`, `deactivate_domain`, `get_domain_config` |
| **Domain** | `add_domain`, `remove_domain` |
| **Source** | `add_source` (idempotent), `add_sources` (batch), `remove_source`, `test_source`, `list_sources`, `get_source_health`, `get_feeds` |
| **Topic** | `add_topic`, `remove_topic`, `list_topics`, `topic_group_add`, `topic_group_remove`, `list_keywords`, `approve_keyword`, `reject_keyword`, `suggest_keywords` |
| **Collection** | `collect_sources` (supports `dry_run=true`, domain-less), `get_collection_progress`, `get_collection_status`, `process_collection` (with batch, check_factual, check_translation), `get_processing_progress`, `batch_run`, `clean_cache` |
| **KB** | `search_knowledge_base` (hybrid/mode=vector/mode=faceted, cross-domain), `get_kb_entry`, `list_summaries`, `get_summary`, `create_kb_entry`, `create_kb_draft` (from Raw only), `reject_kb_draft`, `list_kb_tier`, `reindex_kb`, `flag_for_knowledge_base` |
| **KB Relations** | `link_items`, `get_item_relations` |
| **KB Versioning** | `get_entry_history`, `restore_entry_version` |
| **KB Monitor** | `get_collection_stats`, `get_collection_diff` |
| **KB Graph** | `query_knowledge_graph`, `knowledge_graph_export` |
| **Output** | `list_output_templates`, `generate_digest` (md/html/json/agent), `generate_report` (md/json/pdf/html/audio/agent), `generate_cross_domain_report`, `generate_tutorial`, `generate_presentation`, `localize_content` |
| **Export/Import** | `export_kb` (md/json/sqlite/pdf/csv/graphml/agent/bundle), `import_kb` |
| **CEFR** | `classify_cefr` (EN/ZH/JA), `cefr_batch` |
| **Keywords** | `approve_keyword`, `reject_keyword`, `suggest_keywords` |
| **Email** | `send_email_digest`, `email_config` |
| **Audit** | `query_audit_log` |
| **Q&A** | `query_collected` |
| **Custom Extraction** | `extract_fields`, `get_extraction` |
| **Cron** | `list_schedules`, `add_schedule`, `remove_schedule`, `run_schedules`, `get_schedule_status` |
| **Source Health** | `get_source_health`, `rate_item` |
| **Projects** | `init_project`, `list_projects`, `get_project_assets`, `archive_project` |
| **Monitor** | `list_active_collections`, `list_active_deliveries`, `get_channel_health` |
| **Webhooks** | `set_domain_webhooks`, `get_domain_webhooks` |
| **Quality Gate Config** | `get_gate_config`, `set_gate_config` |
| **Product** | `list_products`, `get_product` |
| **Alert Rules** | `add_alert_rule`, `get_alert_rules`, `remove_alert_rule` |
| **End User** | `send_to_enduser`, `get_enduser_history`, `get_enduser_products`, `query_delivery_log`, `get_delivery_log`, `activate_trial`, `check_trial_expiry`, `update_preferences`, `get_preferences`, `get_subscription_status` |
| **Cost** | `get_billing_summary`, `get_budget_thresholds`, `set_budget_thresholds`, `create_checkout_session`, `get_enduser_usage`, `get_enduser_invoice`, `cost_dashboard`, `cost_allocation` |
| **Data Privacy** | `soft_delete_entry` (with purge flag), `restore_entry`, `export_user_data`, `delete_user_data` |
| **Knowledge Lifecycle** | `compare_versions`, `find_similar_items`, `merge_items`, `get_domain_decay`, `mark_stale`, `calculate_freshness_score`, `recommend_content`, `simplify_content` |
| **Observability** | `trace_item`, `get_metrics`, `get_prometheus_metrics`, `diagnose_system` |
| **Agent Callbacks** | `set_agent_callback`, `list_agent_callbacks`, `remove_agent_callback` |
| **Delivery Schedule** | `add_delivery_schedule`, `list_delivery_schedules`, `remove_delivery_schedule` |
| **Validation** | `list_validation_scenarios`, `run_validation_scenario` |

## Common Workflows

### Set up tracking for a new domain
```
list_domains() → see available domains
get_domain_schema("medical-research") → see extraction fields
activate_domain("medical-research") → load demo config
```

### Add a custom domain from scratch
```
add_domain(name="my-custom-domain", description="...")
list_available_platforms() → discover supported source types
add_source(domain="my-custom-domain", name="my-rss", type="rss", url="...")
add_topic(domain="my-custom-domain", name="My Topic", keywords=["kw1", "kw2"])
collect_sources(domain="my-custom-domain")
```

### Preview before collecting
```
collect_sources(domain="medical-research", dry_run=true)
→ Returns estimated item count without consuming API quota
```

### Collect, process, and review
```
collect_sources(domain="medical-research", topic="IVF")
get_collection_progress(job_id="...") → poll until done
process_collection(domain="medical-research")
list_summaries(domain="medical-research", date_from="today")
```

### Build knowledge base
```
flag_for_knowledge_base(summary_id, tags=["ivf", "breakthrough"])
create_kb_draft(raw_ids=["..."], title="...", summary="...")
→ User promotes Draft→Wiki
```

### Search with hybrid mode
```
search_knowledge_base(domain="medical-research", query="embryo", mode="hybrid")
search_knowledge_base(domain="medical-research", mode="faceted",
  filters={"source_type": "pubmed", "relevance_min": 70})
query_knowledge_graph(domain="medical-research", entity="CRISPR")
```

### Generate and deliver output
```
generate_digest(domain="medical-research", period="week")
generate_report(domain="medical-research", format="pdf", topic="IVF breakthroughs")
generate_presentation(domain="medical-research", topic="Latest Findings")
send_email_digest(to="user@example.com", subject="Weekly Digest", body=digest)
```

### Compare changes over time
```
get_collection_stats(period="week")
get_collection_diff(domain="medical-research", since_collection_id="...")
```

### Check system health
```
diagnose_system() → all-in-one health check
→ returns {health_score: 0-100, phase: init|collect|process|healthy|degraded, ...}
→ on degraded status, inspect `phase` to identify the failing stage
```

### Configure the LLM (BYOK)
```
configure_llm(api_key="sk-...", provider="openai", model="gpt-4")
→ stores an env var reference (${AUTOINFO_LLM_API_KEY}), never the raw key
→ if the key is missing, LLM-required tools return LLM_NOT_CONFIGURED (see Error Handling)
```

### Handle tool errors
```
All MCP tools return the canonical envelope:
  success: {success: true, data: ...}
  error:   {success: false, error: {code, message, actionable}}

When a tool fails:
1. Read error.code → classify the failure (DOMAIN_NOT_FOUND, LLM_NOT_CONFIGURED, ...)
2. If actionable is true → follow the remediation hint in error.message
3. For LLM_NOT_CONFIGURED → run configure_llm() first
4. process_collection with no cached items returns {status: "noop", total_items: 0} — not an error, collect first
```

### Configure quality gates
```
get_gate_config(domain="medical-research") → current gate settings
set_gate_config(domain="medical-research",
  gates={"G3": {"action": "pass", "threshold": 50}}) → customize
```

### Manage alert rules
```
add_alert_rule(domain="medical-research", name="source-down",
  condition="source_health == error", action="email")
get_alert_rules(domain="medical-research") → current rules
remove_alert_rule(domain="medical-research", rule_id="...")
```

### End User lifecycle management

**Create a new End User (starts in trial):**
```
send_to_enduser(name="Acme Corp", email="admin@acme.com",
  tier="pro", delivery_preferences={"channels": ["email", "webhook"]})
```

**Manage delivery preferences:**
```
update_preferences(user_id="usr_xxx",
  delivery_preferences={"channels": ["telegram", "email"],
    "quiet_hours": {"start": "22:00", "end": "07:00", "timezone": "Asia/Shanghai"}})
```

**Check subscription status:**
```
get_subscription_status(end_user_id="usr_xxx")
```

**View cost vs. budget:**
```
get_billing_summary(user_id="usr_xxx", period="month")
cost_dashboard(period="month")
cost_allocation(domain="medical-research", strategy="usage-based")
```

**Trace a delivery issue:**
```
trace_item(trace_id="uuid-xxx") → full pipeline history
```

**GDPR data actions:**
```
export_user_data(user_id="usr_xxx") → full data export
soft_delete_entry(entry_id="kb_xxx") → mark entry deleted
restore_entry(entry_id="kb_xxx") → restore soft-deleted entry
```

### Manage products & delivery
```
list_products(domain="medical-research", type="processed")
get_product(domain="medical-research", product_id="prod_xxx")
```

### Set up webhook notification
```
set_domain_webhooks(domain="medical-research",
  webhooks=[{"url": "https://example.com/hook", "events": ["item.collected"]}])
get_domain_webhooks(domain="medical-research")
```

### Schedule recurring collection
```
add_schedule(domain="medical-research", cron="0 8 * * 1", topic="IVF breakthroughs")
list_schedules()
run_schedules() → manual trigger
```

### Classify content by CEFR level
```
classify_cefr(text="The mitochondria is the powerhouse of the cell.", language="en")
→ returns {"level": "B2", "confidence": 0.87}
```

### Custom field extraction
```
extract_fields(domain="medical-research", text="...",
  schema={"fields": [{"name": "dosage", "type": "string"}]})
get_extraction(extraction_id="ext_xxx")
```

### KB versioning & history
```
get_entry_history(entry_id="kb_xxx") → full version history
restore_entry_version(entry_id="kb_xxx", version=2) → rollback
```

### KB import
```
import_kb(domain="medical-research", file_path="/path/to/doc.pdf", format="pdf")
```

### View billing summary
```
get_billing_summary(user_id="usr_xxx", period="month")
→ returns total spend, per-model costs, budget status
```

### Monitor active deliveries
```
list_active_deliveries()
→ returns in-flight deliveries with status and retry info
get_delivery_log(subscription_id="sub_xxx", period="week")
→ returns delivery history with SLA compliance metrics
```

### Manage knowledge lifecycle
```
# Merge duplicate entries
find_similar_items(domain="medical-research", query="embryo", threshold=0.85)
merge_items(primary_id="kb_001", secondary_ids=["kb_002"], mode="llm")

# Check domain freshness & decay
get_domain_decay(domain="medical-research")
calculate_freshness_score(entry_id="kb_001")
mark_stale(entry_id="kb_001")

# Compare versions
compare_versions(entry_id="kb_001", v1="1", v2="2")
```

### Use Agent Callbacks (push delivery)
```
set_agent_callback(url="https://my-agent.example.com/callback",
  events=["new_digest", "new_report"])
list_agent_callbacks()
remove_agent_callback(callback_id="cb_xxx")
```

## Important Constraints

| Rule | Detail |
|------|--------|
| **DO NOT write to 03-Wiki** | Only human can promote Draft→Wiki. |
| **DO NOT create Draft from nothing** | Must come from 01-Raw (call `create_kb_draft` with `raw_ids`). |
| **DO NOT run `init` or store raw API keys** | Use `init_project` MCP tool (not CLI init) and `configure_llm()` for BYOK — it stores `${AUTOINFO_LLM_API_KEY}` as an env var reference, never the raw key. |
| **DO NOT delete sources or domains** | Ask human first. |
| **DO NOT edit `.autoinfo/config.yaml` directly** | Use MCP tools (`add_source`, `add_topic`, etc.). |
| **DO NOT run `autoinfo doctor`** | Use `diagnose_system()` MCP tool instead. |
| **DO NOT permanently delete End Users** | Use `get_subscription_status` / `update_preferences` to manage. Only Director User can purge. |
| **DO NOT demote Wiki entries** | Wiki is append-only. Tag `deprecated` only upon explicit human command. |

## Authorization Boundaries

```
┌─────────────────────────────────────────────────────┐
│                    DIRECTOR USER (Human)              │
│  Can: promote Draft→Wiki, delete domains/sources,    │
│        purge End User data, manage API keys,         │
│        override any agent action, approve/reject     │
├─────────────────────────────────────────────────────┤
│                    DIRECT USER (You / Agent)          │
│  Can: all COLLECT/PROCESS/SEARCH/DELIVER operations, │
│        create Draft from Raw, manage End Users       │
│        (create/update/suspend/cancel, NOT purge),    │
│        soft-delete/restore KB entries, manage alerts,│
│        configure quality gates, import/export KB     │
├─────────────────────────────────────────────────────┤
│                    END USER (Paying Customer)         │
│  Can: receive products via configured channels,      │
│        manage own preferences (via portal CLI),      │
│        access own product archive, view own cost     │
│        CANNOT: operate AutoInfo directly             │
└─────────────────────────────────────────────────────┘
```
