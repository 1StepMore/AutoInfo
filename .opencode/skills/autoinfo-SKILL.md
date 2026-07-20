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
```

You are the interface. The human tells you what they want tracked, and
you translate that into AutoInfo tool calls.

## Tool Discovery

Not sure what tools exist? Use MCP protocol discovery.
Key categories:

| Category | Key Tools |
|----------|-----------|
| System | `health_check`, `diagnose_system`, `list_available_models` |
| Domain | `list_domains`, `get_domain_schema`, `activate_domain` |
| Source | `add_source`, `add_sources`, `test_source`, `get_source_health` |
| Topic | `list_topics`, `add_topic`, `list_keywords` |
| Collection | `collect_sources` (supports `dry_run=true`), `get_collection_diff` |
| KB | `search_knowledge_base`, `get_kb_entry`, `create_kb_draft`, `list_kb_tier` |
| Output | `generate_digest`, `generate_tutorial`, `list_output_templates` |

## Common Workflows

### Set up tracking for a new domain
```
list_domains() → see available domains
get_domain_schema("medical-research") → see extraction fields
activate_domain("medical-research") → load demo config
```

### Preview before collecting
```
collect_sources(domain="medical-research", dry_run=true)
→ Returns estimated item count without consuming API quota
```

### Collect, process, and review
```
collect_sources(domain="medical-research", topic="IVF")
get_collection_progress(collection_id) → poll until done
process_collection(domain="medical-research")
list_summaries(domain="medical-research", date_from="today")
```

### Build knowledge base
```
flag_for_knowledge_base(summary_id, tags=["ivf", "breakthrough"])
create_kb_draft(raw_ids=["..."], title="...", summary="...")
→ User promotes Draft→Wiki
```

### Compare changes
```
get_collection_stats(period="week")
get_collection_diff(domain="medical-research", since_collection_id="...")
```

### Check system health
```
diagnose_system()  → all-in-one health check
```

## Important Constraints

- **DO NOT** write to 03-Wiki. Only human can promote Draft→Wiki.
- **DO NOT** create Draft from nothing — must come from 01-Raw.
- **DO NOT** run `init` or manage API keys — those are human operations.
- **DO NOT** delete sources or domains — ask human first.
- **DO NOT** edit `.autoinfo/config.yaml` directly — use `add_source`, `add_topic` etc.
