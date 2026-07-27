# Three-User Authorization & Escalation Matrix

**Purpose**: Single reference for what each user type can do, who to escalate to,
and handoff protocols. Consolidates rules from F20, F36-F40, F47, F53,
`director-user-guide.md`, `AGENTS.md`, and `autoinfo-skill/SKILL.md`.

## Role Definitions

| Role | Alias | Interface | Operates |
|------|-------|-----------|----------|
| **Director User** | Human commander | Natural language ↔ Agent | **Agent** (who operates AutoInfo), plus human-only CLI/MCP |
| **Direct User** | Agent / Operator | MCP tools | **AutoInfo Server** directly |
| **End User** | Paying customer | Receives products via delivery channels, manages preferences via portal CLI | **Own profile** only (self-service) |

## Interaction Chain

```
Director User (Human)
    │  natural language
    ▼
Direct User (Agent) ──MCP tools──> AutoInfo Server ──delivery──> End User
    │                                                                │
    │  escalation / override                                         │  self-service portal
    ◄──────────────────────────── Human decides ────────────────────  │
```

## Authorization Matrix

| Operation | Director User (Human) | Direct User (Agent) | End User | Reference |
|-----------|----------------------|---------------------|----------|-----------|
| **Init project** | ✅ CLI `autoinfo init` | ✅ MCP `init_project` | ❌ | F01 |
| **LLM config / API keys** | ✅ Configure manually | ❌ Must not manage keys | ❌ | AGENTS.md |
| **Source CRUD** | ✅ CLI `sources` | ✅ MCP `add_source`/`remove_source` | ❌ | F07 |
| **Topic CRUD** | ✅ CLI `topics` | ✅ MCP `add_topic`/`remove_topic` | ❌ | F09 |
| **Collection (fetch)** | ✅ CLI `collect` | ✅ MCP `collect_sources` | ❌ | F11 |
| **Processing (LLM)** | ✅ CLI `process` | ✅ MCP `process_collection` | ❌ | F13 |
| **Raw → Draft** | ✅ via promote flow | ✅ MCP `create_kb_draft` | ❌ | F20 |
| **Draft → Wiki** | **✅ ONLY human** | ❌ **MUST NOT** write to 03-Wiki | ❌ | F20 (hard rule) |
| **Wiki deprecate** | ✅ | ✅ only on explicit human command | ❌ | F20 |
| **Demote/delete Wiki** | **✅ ONLY human** | ❌ | ❌ | F20 (append-only) |
| **Summary flag/reject** | ✅ | ✅ MCP `flag_for_knowledge_base`, `reject_kb_draft` | ❌ | F16 |
| **Output generation** | ✅ CLI `output` | ✅ MCP `generate_*` | ❌ | F24-F28 |
| **End User Create** | ✅ | ✅ MCP `create_end_user` | ❌ (provisioned by operator) | F36 |
| **End User Read** | ✅ | ✅ MCP `get_end_user` | ✅ (own profile only) | F36 |
| **End User Update** | ✅ | ✅ MCP `update_end_user` (with audit trail) | ✅ (own preferences only) | F36 |
| **End User Suspend** | ✅ | ✅ MCP `update_end_user(status="suspended")` | ❌ | F38 |
| **End User Cancel** | ✅ | ✅ MCP `update_end_user(status="cancelled")` | ❌ | F38 |
| **End User Delete (soft)** | ✅ | ✅ (deactivate, not purge) | ❌ | F47 |
| **End User Purge (permanent)** | **✅ ONLY human** with `--purge` | ❌ Agent cannot purge | ❌ | F47 |
| **KB Entry Delete (soft)** | ✅ | ✅ MCP `soft_delete_entry` | ❌ | F47 |
| **KB Entry Restore** | ✅ | ✅ MCP `restore_entry` | ❌ | F47 |
| **GDPR Export** | ✅ | ✅ MCP `export_user_data` | ✅ (own data) | F47 |
| **Quality Gate Config** | ✅ | ✅ MCP `set_gate_config` | ❌ | G0-G5 |
| **Alert Rule CRUD** | ✅ | ✅ MCP `add_alert_rule`/`remove_alert_rule` | ❌ | F54 |
| **Webhook Setup** | ✅ | ✅ MCP `set_domain_webhooks` | ❌ | — |
| **Cron Schedule** | ✅ | ✅ MCP `add_schedule`/`remove_schedule` | ❌ | F32 |
| **Domain Add/Remove** | **✅ ONLY human** | ❌ Must ask human first | ❌ | F07 |
| **Source Remove** | **✅ ONLY human** | ❌ Must ask human first | ❌ | F07 |
| **Merge Entries** | ✅ | ✅ MCP `merge_items` (creates Draft) | ❌ | F53 |
| **Merge → Wiki** | **✅ ONLY human** | ❌ Merged entry is Draft-tier | ❌ | F53 (trust boundary) |
| **Cross-Collection Dedup** | ✅ | ✅ (LLM-assisted, human promotion) | ❌ | F53 |
| **Cost Report View** | ✅ | ✅ MCP `get_cost_report` | ✅ (own cost only) | F43 |
| **Budget Alert Config** | ✅ | ✅ MCP `add_alert_rule` (budget type) | ❌ | F45 |
| **Portal Access** | ✅ | ❌ Agent operates on behalf | ✅ (own portal CLI) | F40 |

## Escalation Paths

### When Agent Cannot Decide

```
Agent encounters ambiguous request
    │
    ▼
Agent asks clarifying question (1 question maximum)
    │
    ▼
Human provides clarification
    │
    ▼
Agent proceeds
```

Reference: `director-user-guide.md` §4 (Intent Capture & Clarification),
validation Part 14 Q66.

### Source Health Failure → Human Decision

```
Agent detects source failure (polling or webhook alert)
    │
    ▼
Agent informs human: "Source X has failed N times. Options:
  1. Retry (automatic)
  2. Replace source (requires your config)
  3. Disable source (requires your action)
  4. Ignore N failures"
    │
    ▼
Human decides → Agent executes
```

Reference: `agent-alerting.md`, validation Part 14 Q67.

### Budget Threshold → Auto-Remediation (then Escalate)

```
Cost crosses budget threshold
    │
    ▼
If < 100%: warning alert to Director User
If ≥ 100% (critical):
    1. Auto-pause collections
    2. Auto-switch to cheaper LLM model
    3. Notify Director User
    │
    ▼
Director User reviews, may override auto-remediation
```

Reference: `expectations.md` F45, `operations.md` §1.4.

### Human Override of Agent Action

```
Agent performs action
    │
    ▼
Human says "stop" or "undo" or "change that"
    │
    ▼
Agent: stops immediately, confirms current state,
presents options to revert or modify
    │
    ▼
Human confirms → Agent executes reversal
```

Reference: `director-user-guide.md` §9 (Override & Compliance),
validation Part 14 Q69.

### End User Issue → Agent → Director User

```
End User reports issue (delivery failure, wrong content, etc.)
    │
    ▼
Agent investigates: trace_item(trace_id), check delivery logs,
check quality gate results
    │
    ▼
Agent can resolve autonomously:
  - Re-trigger failed delivery
  - Adjust quality gate thresholds
  - Soft-delete incorrect entries
    │
    ▼
If issue requires human authority:
  - Permanent data purge → escalate to Director User
  - Domain/source config change → escalate to Director User
  - Wiki content correction → escalate to Director User
```

Reference: `expectations.md` F47, F53, `director-user-guide.md` §8.

## What Agent Can Do Automatically (Without Asking)

| Category | Actions |
|----------|---------|
| **Collection** | Collect, process, search, browse, Q&A |
| **KB Draft** | Create Draft from Raw, soft-delete, restore, merge (creates Draft) |
| **Output** | Generate digests, reports, presentations, tutorials, translations |
| **End User** | Create, read, update (with audit), suspend, cancel, list |
| **Cost** | View reports, allocation, set budget alerts |
| **Quality** | Get/set gate configuration |
| **Alerts** | Add/list/remove alert rules |
| **Webhooks** | Set/get webhooks |
| **Cron** | Add/list/remove schedules |
| **CEFR** | Classify text |
| **Custom Extraction** | Extract fields |
| **Import/Export** | Import KB, export KB |
| **Monitoring** | Health check, diagnostics, metrics, trace |

## What Agent Must Ask Human Before Doing

| Operation | Why |
|-----------|-----|
| **Delete source** | Irreversible config change |
| **Delete domain** | Irreversible config change |
| **Purge End User data** | Permanent deletion, legal implications |
| **Demote/delete Wiki** | Violates append-only contract |
| **Edit config files directly** | Use MCP tools instead |
| **Init API keys** | Human-managed secrets |

## What Only Human Can Do

| Operation | Reason |
|-----------|--------|
| **Promote Draft → Wiki** | Wiki entries are permanently reviewed knowledge |
| **Permanent data purge** | Irreversible, legal implications |
| **Remove domain/source** | Strategic configuration decision |
| **Manage API keys/secrets** | Security boundary |
| **CLI `init` without MCP** | Alternative workflow for human preference |

## References

- `docs/dev/specs/expectations.md` — F20 (KB pipeline), F36-F40 (End User), F47 (Data Privacy), F53 (Dedup & Merge)
- `docs/dev/director-user-guide.md` — Full Director User interaction lifecycle
- `AGENTS.md` — Agent constraints (MUST NOT), architecture rules
- `docs/skills/autoinfo-skill/SKILL.md` — Agent operation skill with auth boundaries
- `docs/dev/agent-alerting.md` — Agent proactive alerting escalation
- `docs/dev/specs/operations.md` — Data privacy, cost governance rules
- `docs/autoinfo-validation-master-plan-v2/part-14-human-agent-collaboration.md` — Validation scenarios for escalation paths
