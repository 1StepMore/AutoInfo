<!-- agent: multi-tenancy-auth-spec -->
# Multi-Tenancy, Authentication, Rate Limiting & Admin Dashboard

> **Deferral note:** Current MCP server is stdio-only — auth deferred until SSE transport.
> The spec below is architectural design only. No code paths enforce tenant isolation,
> API key validation, or rate limiting while the server runs over stdio (assumed trusted process).
> Implementation work is gated on the SSE transport milestone.

> **Date:** 2026-07-27
> **Version:** v1.0-draft (Never Designed — spec only, zero implementation)
> **Status:** 🔴 Never Designed — Type 1 Gap. All content in this document is architectural specification for yet-to-be-built systems.
> **Forward status:** Planned. F58-F69 (multi-tenancy, auth, rate limiting, admin dashboard, notification framework; see [`expectations.md`](./expectations.md)) are deliberately deferred, not merely un-designed: `user_id` fields exist as advisory foundation only. Full multi-tenancy/auth/RBAC is a roadmap item, not a current capability. Implementation remains gated on the SSE transport milestone.
>
> This spec covers four cross-cutting concerns that are entirely absent from the AutoInfo codebase:
> multi-tenancy data isolation, end-user authentication, API rate limiting, and a web-based admin dashboard.
> These were identified in the [`cross-dimensional-catalog.md`](../cross-dimensional-catalog.md) as
> CD-001 (Multi-Tenancy Isolation), CD-002 (End-User Authentication), CD-003 (Rate Limiting / Abuse Prevention),
> CD-005 (Admin Dashboard), CD-013 (Live Operations Dashboard), CD-021 (Identity Anchor), and CD-042 (Multi-Tenant Data Isolation).
>
> Data model schemas referenced herein are defined in [`data-models.md §6`](./data-models.md#6-auth--multi-tenancy-models)
> (`Tenant`, `ApiKey`, `UserSession`, `RateLimit`). Identity anchor definitions are in
> [`delivery.md §4.3`](./delivery.md#43-identity-anchors).
>
> **No implementation exists.** `user_id` fields on entries are advisory, not enforced.
> SQLite is shared across all users/tenants with no isolation. The REST API has no authentication (localhost security only).
> Zero rate-limiting code exists. No admin dashboard.

---

## Table of Contents

1. [§1: Multi-Tenancy Model](#1-multi-tenancy-model)
2. [§2: End-User Authentication](#2-end-user-authentication)
   - [§2.6: Agent Identity](#26-agent-identity)
3. [§3: Rate Limiting & Abuse Prevention](#3-rate-limiting--abuse-prevention)
4. [§4: Admin Dashboard](#4-admin-dashboard)
5. [§5: Implementation Roadmap](#5-implementation-roadmap)

---

## §1: Multi-Tenancy Model

> Cross-ref: [CD-001 (Multi-Tenancy Isolation)](../cross-dimensional-catalog.md#cd-001-multi-tenancy-isolation),
> [CD-042 (Multi-Tenant Data Isolation)](../cross-dimensional-catalog.md#cd-042-no-multi-tenant-data-isolation).

### 1.1 Current Reality (Gap Description)

```code_evidence
# src/autoinfo/kb.py, src/autoinfo/models.py
# user_id fields exist but are ADVISORY, not enforcement:
#   - No tenant_id on any model
#   - All KB entries in single SQLite database
#   - No query-level filtering by tenant
#   - REST API has no auth (localhost security only)
#   - MCP tools have no tenant context
# Evidence: grep -r "tenant" src/autoinfo/ returns zero business-logic matches
```

### 1.2 Tenant Isolation Model — Design Decision

AutoInfo will use **shared-database with `tenant_id` column** (application-level isolation) as the v1 strategy, with a
documented migration path to database-per-tenant (or PostgreSQL schema-per-tenant) at scale.

| Strategy | Pros | Cons | V1 Decision |
|----------|------|------|-------------|
| **Database-per-tenant** | Strongest isolation, independent backup/restore, no query mistakes | Operational complexity (N databases), connection pool exhaustion, migration across N DBs | ❌ v2+ only |
| **PostgreSQL schema-per-tenant** | Good isolation, same connection pool, per-schema migration | PostgreSQL dependency, schema management tooling | ❌ v2+ only (requires DB migration) |
| **Shared DB + `tenant_id` column** | Simple, single SQLite file, zero operational overhead, easy to implement | Weakest isolation — all data in one file; query mistakes can leak data; no per-tenant backup | ✅ **v1 choice** |

**V1 Architecture:**

```
┌──────────────────────────────────────────────────────────────┐
│                    AutoInfo Application                      │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Tenant A  │  │ Tenant B  │  │ Tenant C  │  │ Default   │   │
│  │ domain=   │  │ domain=   │  │ domain=   │  │ (single-  │   │
│  │ acme-corp │  │ beta-co   │  │ gamma-ltd │  │ tenant)   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │              │              │              │          │
│       └──────────────┴──────────────┴──────────────┘          │
│                          │                                    │
│              ┌───────────▼───────────┐                        │
│              │   TenantContext       │                        │
│              │   middleware injects  │                        │
│              │   tenant_id to all    │                        │
│              │   queries             │                        │
│              └───────────┬───────────┘                        │
│                          │                                    │
│              ┌───────────▼───────────┐                        │
│              │   Shared SQLite DB    │                        │
│              │   WITH tenant_id cols │                        │
│              └───────────────────────┘                        │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 Tenant-Enforced Query Pattern

Every database query MUST include a tenant filter. The pattern is:

```python
# Anti-pattern (current code — no tenant scoping):
cursor.execute("SELECT * FROM kb_entries WHERE domain = ?", (domain,))

# Required pattern (v2 with multi-tenancy):
cursor.execute(
    "SELECT * FROM kb_entries WHERE tenant_id = ? AND domain = ?",
    (current_tenant.id, domain)
)
```

**Enforcement strategy:**

| Layer | Mechanism | Failure Mode |
|-------|-----------|--------------|
| **Application middleware** | `TenantContext` injected at request/MCP-call boundary. All service/repository methods require `tenant_id` parameter (Positional-only, no default). | `TypeError` at call site if omitted. |
| **Repository layer** | Decorator `@require_tenant` on all data access methods. Validates `tenant_id` is present and matches the active context. | `TenantViolationError` raised before any DB call. |
| **Database layer** | SQLite triggers (optional, v2) — `BEFORE INSERT/UPDATE` trigger validates `tenant_id IS NOT NULL`. | Row rejected at DB level. |
| **Code review** | CI lint rule: any raw SQL without `WHERE tenant_id` clause flagged. | PR blocked. |

### 1.4 KB Access Control Per Tenant

| KB Tier | Tenant A Access | Tenant B Access | Cross-Tenant Access |
|---------|:---:|:---:|:---:|
| 01-Raw | ✅ Read/Write own | ✅ Read/Write own | 🔴 Forbidden |
| 02-Draft | ✅ Read/Write own | ✅ Read/Write own | 🔴 Forbidden |
| 03-Wiki | ✅ Read/Write own (agent promote via `promote_kb_draft`) | ✅ Read/Write own | 🔴 Forbidden |

**Cross-tenant sharing (v3+):** Tenants may explicitly share KB entries to other tenants via a `shared_with: [tenant_ids]` field.
Not in v1 scope.

### 1.5 Data Partitioning Strategy

| Data Category | Partition Key | Notes |
|---------------|:---:|--------|
| **KB Entries** | `tenant_id` | Every KB entry (Raw, Draft, Wiki) has `tenant_id` FK → `Tenant.id`. |
| **Domains, Sources, Topics** | `tenant_id` | Each tenant manages its own domains, sources, and topics. No cross-tenant domain sharing in v1. |
| **End Users** | `tenant_id` | End users belong to a single tenant. See [delivery.md §4](./delivery.md#4-end-user-lifecycle). |
| **Products & Templates** | `tenant_id` | Product templates are tenant-scoped. System templates shipped with AutoInfo are tenant-agnostic (tenant_id = NULL). |
| **Collection Cache** | `tenant_id` | Raw JSON cache in `collections/` is scoped per tenant. File path: `collections/{tenant_slug}/{domain}/`. |
| **Cost Logs** | `tenant_id` | Cost metering is per-tenant for billing allocation. |
| **Audit Logs** | `tenant_id` | Audit entries scoped to tenant; system-wide audit log is separate. |
| **MCP/CLI Sessions** | `tenant_id` | Agent sessions bind to one tenant at a time. |

**Unaffected (tenant-agnostic):**
- System configuration (LLM keys, global rate limits)
- Prometheus metrics (aggregated, with tenant labels)
- Static assets, code, templates shipped with AutoInfo

### 1.6 Tenant Provisioning Workflow

```
1. Operator creates tenant:
   MCP: create_tenant(name="Acme Corp", slug="acme-corp")
   → Tenant record created, SQLite tables initialized
   → Default admin API key generated (shown once)

2. Operator configures tenant:
   MCP: set_tenant_config(tenant="acme-corp", quota={...})
   → Rate limits, storage quotas, data retention set

3. Operator creates users within tenant:
   MCP: create_end_user(tenant="acme-corp", name="Alice", ...)

4. Agent connects with tenant context:
   MCP: list_domains(tenant="acme-corp")
   → All MCP operations scoped to tenant

5. (Optional) Operator suspends tenant:
   MCP: suspend_tenant(tenant="acme-corp", reason="payment overdue")
   → All tenant operations blocked; data retained
```

**Default tenant:** In single-tenant mode (current AutoInfo behavior), all operations use a single implicit default tenant (`tenant_id = "default"`). This ensures backward compatibility. Multi-tenancy is activated by creating a second tenant.

### 1.7 Tenant-Scoped MCP Tools (Proposed)

| Tool | Description |
|------|-------------|
| `create_tenant(name, slug, settings)` | Provision a new tenant. Returns API key. |
| `get_tenant(tenant_slug)` | Get tenant details and configuration. |
| `list_tenants(page, limit)` | Paginated tenant list (admin only). |
| `update_tenant(tenant_slug, settings)` | Update tenant configuration. |
| `suspend_tenant(tenant_slug, reason)` | Suspend tenant (data retained, operations blocked). |
| `reactivate_tenant(tenant_slug)` | Reactivate a suspended tenant. |
| `delete_tenant(tenant_slug)` | Permanently delete tenant and all data (GDPR-compliant confirmation required). |

---

## §2: End-User Authentication

> Cross-ref: [CD-002 (End-User Authentication)](../cross-dimensional-catalog.md#cd-002-end-user-authentication),
> [CD-021 (Identity Anchor)](../cross-dimensional-catalog.md#cd-021-identity-anchor).
> Identity anchor definitions: [delivery.md §4.3](./delivery.md#43-identity-anchors).

### 2.1 Current Reality (Gap Description)

```code_evidence
# src/autoinfo/mcp/server.py, src/autoinfo/api/server.py
# No authentication anywhere:
#   - REST API: no auth (localhost security only)
#   - MCP server: no auth (stdio transport, assumed trusted)
#   - CLI portal: no auth (local filesystem)
#   - activate_trial(enduser_id="...") takes raw ID, no identity verification
#   - send_to_enduser(user_id="...") takes raw ID
# Evidence: grep -ri "auth\|login\|session\|oauth\|jwt\|token" src/autoinfo/mcp/server.py
#           returns zero authentication middleware matches
```

### 2.2 Auth Provider Abstraction

AutoInfo will implement a provider-agnostic authentication layer with pluggable backends:

```
                    ┌─────────────────────────┐
                    │   AuthProvider (ABC)     │
                    │   - authenticate()       │
                    │   - validate_session()   │
                    │   - refresh_session()    │
                    │   - revoke_session()     │
                    └───────────┬─────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
  ┌───────▼───────┐   ┌────────▼────────┐   ┌────────▼────────┐
  │ NativeProvider│   │ OAuthProvider   │   │ MagicLinkProvider│
  │ (email/pw)    │   │ (Google, GitHub,│   │ (email magic     │
  │               │   │  enterprise SSO)│   │  link, no pw)    │
  └───────────────┘   └─────────────────┘   └─────────────────┘
```

**V1 scope:** `NativeProvider` (email + password, bcrypt hashed) and `MagicLinkProvider` (passwordless email links). OAuth deferred to v2.

| Provider | V1? | Description | Configuration |
|----------|:---:|-------------|---------------|
| **Native (email/password)** | ✅ | Email + password. bcrypt hash stored in `UserProfile.password_hash`. | Default for operator-created users. |
| **Magic Link (email)** | ✅ | One-time link sent via email. 15-minute expiry. No password stored. | Good for end-user self-service (portal login). |
| **OAuth 2.0 / OIDC** | ❌ v2 | Google, GitHub, enterprise SSO providers. | Requires OAuth client config per provider. |
| **API Key** | ✅ | Static key for programmatic access (MCP/CLI agents). Hashed with SHA256. | See [data-models.md §6 `ApiKey`](./data-models.md#6-auth--multi-tenancy-models). |

### 2.3 Session Management

```
┌─ Login Flow ───────────────────────────────────────────────┐
│                                                             │
│  1. Client sends credentials (email+password or magic link) │
│  2. AuthProvider.authenticate() → UserProfile + Tenant       │
│  3. Create UserSession:                                     │
│     - Generate session_token (opaque, 256-bit random)       │
│     - Store token_hash = SHA256(token) in DB                │
│     - Set expires_at = now + 24h                            │
│     - Return token + session metadata to client              │
│  4. Client stores token (HTTP-only cookie / Bearer header)  │
│                                                             │
├─ Request Flow ──────────────────────────────────────────────┤
│                                                             │
│  1. Client sends request with token                         │
│  2. Middleware:                                             │
│     - Extract token from header/cookie                      │
│     - token_hash = SHA256(token)                            │
│     - Lookup UserSession WHERE token_hash = ? AND is_active │
│     - Check expires_at > now()                              │
│     - Inject TenantContext(user_id, tenant_id, session_id)  │
│  3. Handler executes with tenant/user context               │
│                                                             │
├─ Token Refresh ─────────────────────────────────────────────┤
│                                                             │
│  1. When token is within 1h of expiry, client may refresh   │
│  2. refresh_session(old_token) → new token, new expiry      │
│  3. Old token invalidated                                   │
│  4. Max refresh chain: 7 days (then full re-login required) │
│                                                             │
├─ Logout / Revoke ───────────────────────────────────────────┤
│                                                             │
│  1. revoke_session(token) → set is_active = false           │
│  2. revoke_all_user_sessions(user_id) → all tokens revoked  │
│  3. Scheduled cleanup: expired tokens deleted after 7 days  │
└─────────────────────────────────────────────────────────────┘
```

**Session token characteristics:**

| Property | Value |
|----------|-------|
| Token format | Opaque random string (256-bit, 43 base64url chars) |
| Storage | SHA256 hash in DB; raw token returned once to client |
| Default TTL | 24 hours |
| Refresh TTL | 7 days (max chain) |
| Cookie name | `autoinfo_session` (HTTP-only, Secure, SameSite=Lax) |
| Header name | `Authorization: Bearer <token>` |
| Max concurrent | 5 sessions per user (oldest evicted on 6th) |

### 2.4 MCP Tool Auth Flow

The MCP server currently operates over stdio with no authentication (assumed trusted process). For multi-tenant deployments, agents need tenant-scoped credentials:

```
Agent ──MCP stdio──> AutoInfo MCP Server
                      │
                      ├── Header: X-AutoInfo-Tenant: acme-corp
                      ├── Header: X-AutoInfo-API-Key: apk_xxxx
                      │
                      ├── TenantContext injected from API key lookup
                      ├── All MCP operations scoped to tenant
                      │
                      └── API key permissions enforced per call

API Key Permission Model:
  apk_xxxx → {
    tenant_id: "tnt_acme",
    permissions: ["kb:read", "kb:write", "collection:run", "delivery:send"],
    expires_at: "2027-01-01",
    rate_limit: { requests_per_minute: 60 }
  }
```

**Agent auth flow:**

1. Operator creates API key for tenant via MCP: `create_api_key(tenant="acme-corp", name="Production Agent", permissions=["kb:*", "collection:*"])`
2. Raw key shown once; agent stores it in environment: `export AUTOINFO_API_KEY="apk_xxxx_..."` `export AUTOINFO_TENANT="acme-corp"`
3. MCP client reads env vars and passes as headers on every MCP call
4. Server validates: API key → tenant → permissions → rate limit

**Permission scopes:**

| Scope | Access |
|-------|--------|
| `kb:read` | Read KB entries, search, Q&A |
| `kb:write` | Create Draft, flag items, link items |
| `kb:admin` | Reindex KB, restore entries, merge items |
| `collection:run` | Trigger collection, process collection |
| `collection:manage` | Add/remove sources, topics, schedules |
| `delivery:send` | Generate and send products |
| `delivery:manage` | Configure channels, subscriptions, end users |
| `admin:users` | Create/manage end users (within tenant) |
| `admin:tenant` | Update tenant settings, billing, quotas |
| `admin:system` | System-wide operations (diagnostics, global config) |

### 2.5 Identity Anchor

> Cross-ref: [CD-021 (Identity Anchor)](../cross-dimensional-catalog.md#cd-021-identity-anchor).
> Full definition in [delivery.md §4.3](./delivery.md#43-identity-anchors).

The identity anchor is the source-of-truth for user uniqueness. Every `UserProfile` has exactly one identity anchor, set at creation and never changed:

| Anchor Type | Format | V1? | Use Case |
|-------------|--------|:---:|----------|
| `native` | `native` | ✅ | Operator-created users (v1 default). No external identity provider. |
| `email` | `email:{email}` | ✅ | Email-verified users (magic link or password). Email uniqueness enforced. |
| `oauth` | `oauth_provider:{provider}:{sub}` | ❌ v2 | OAuth-idP authenticated users. Provider-scoped uniqueness. |
| `source_platform` | `platform:{platform}:{user_id}` | ❌ v2 | Delivery channel identity (Telegram chat ID, WeChat OpenID, etc.). See delivery.md §4.3 spec gap: field is spec'd but not implemented. |

**Design invariants:**

- Identity anchor is immutable after creation. No merging of identities in v1.
- Email uniqueness is enforced at `UserProfile` creation when anchor type is `email`.
- A user with `native` anchor can later add `email` anchor if email is verified. This creates an identity link, not a merge.
- `source_platform + source_user_id` pattern (from delivery.md §1.1) provides cross-channel identity resolution when end users interact via multiple delivery channels.

### 2.6 Agent Identity

> Cross-ref: [CD-021 (Identity Anchor)](../cross-dimensional-catalog.md#cd-021-identity-anchor),
> [§2.4 MCP Tool Auth Flow](#24-mcp-tool-auth-flow).

The identity anchor in §2.5 covers end users. Agents (the AI clients driving MCP tool
calls) need a parallel identity model. This subsection specifies how agent identity is
derived and enforced once authentication is enabled. **No implementation exists today** —
the stdio transport assumes a single trusted caller.

**Derivation rule:** Agent identity derives from the API key presented on the MCP connection.
A single API key resolves to exactly one `(tenant_id, agent_id)` pair. The key is the only
credential an agent presents; no separate agent login or token exchange is required.

```
API Key (apk_xxxx)
   │
   ├── tenant_id   →  scopes all data access (§1)
   ├── agent_id    →  derived from key metadata at creation time
   ├── permissions →  scopes allowed MCP tools (§2.4)
   └── rate_limit  →  per-agent quota (§3)
```

**Agent identity vs end-user identity:**

| Aspect | End User (§2.5) | Agent (§2.6) |
|--------|-----------------|--------------|
| Identity anchor | `native` / `email` / `oauth` / `source_platform` | API key fingerprint (`apikey:{key_id}`) |
| Set by | Operator or self-service | Operator at API key creation |
| Mutability | Immutable after creation | Rotated by operator (new key = new agent_id, or same agent_id if key metadata links them) |
| Scope of access | Own profile, subscriptions, deliveries | Tenant-wide MCP operations per permissions |
| Rate limit subject | Per-user delivery quotas | Per-agent request quotas |

**Design invariants:**

- One API key maps to one agent identity. No key sharing across agents. If an operator
  provisions a second agent, a second key is issued.
- `agent_id` is recorded in the audit log alongside `tenant_id` for every MCP call, so
  traceability (per-item `trace_id`) extends to "which agent did this".
- Rate limiting (§3) is enforced per-agent, not per-tenant. A tenant with three agents
  gets three quotas, not one shared pool. This prevents a single chatty agent from
  starving the tenant's other agents.
- Agent identity is invisible to end users. End users see products and deliveries, never
  the agent that triggered generation.
- When the SSE transport lands and auth is enabled, existing stdio callers must migrate
  to an API key. The stdio path remains available for local single-tenant use without auth,
  preserving the current developer experience.

---

## §3: Rate Limiting & Abuse Prevention

> Cross-ref: [CD-003 (Rate Limiting / Abuse Prevention)](../cross-dimensional-catalog.md#cd-003-rate-limiting--abuse-prevention).

### 3.1 Current Reality (Gap Description)

```code_evidence
# Zero rate limiting anywhere in the codebase:
#   - collect_sources: no limit on concurrent collections
#   - process_collection: no limit on LLM API calls
#   - batch_run: no concurrency cap
#   - MCP tools: no per-call rate limit
#   - REST API: no throttling
#   - Evidence: grep -ri "rate.limit\|throttle\|backoff\|429\|too.many.requests" src/autoinfo/
#             returns zero rate-limiting middleware or enforcement code
```

### 3.2 Rate Limiting Strategy — Sliding Window

AutoInfo will use a **sliding window** approach for rate limiting, tracking a counter per `(tenant_id, endpoint, window_start)` tuple.

| Approach | Pros | Cons | Choice |
|----------|------|------|:---:|
| **Token bucket** | Smooth burst handling, simple model | Requires periodic token refill, stateful | ❌ |
| **Fixed window** | Simplest, atomic counter reset | Thundering herd at window boundary | ❌ |
| **Sliding window** | No boundary spike, accurate rate measurement | Slightly more state (current + previous window) | ✅ **v1** |
| **Leaky bucket** | Constant outflow, good for queue-based | Complex to tune, queue overflow | ❌ v2 |

**Sliding window algorithm:**

```
requests_in_window = current_window_count * (1 - elapsed_ratio) + previous_window_count * elapsed_ratio

if requests_in_window >= limit:
    → 429 Too Many Requests
    → Retry-After: window_remaining_seconds
    → block until next window
```

### 3.3 Rate Limit Tiers

| Tier | Scope | Default Limit | Window | Hard/Soft | Enforcement Point |
|------|-------|:---:|--------|:---:|-------------------|
| **Global** | All tenants combined | 10,000 req/min | 60s | 🔴 Hard | API gateway / MCP server |
| **Per-Tenant** | Single tenant | 1,000 req/min | 60s | 🔴 Hard | TenantContext middleware |
| **Per-User/API-Key** | Single API key or session | 100 req/min | 60s | 🔴 Hard | Auth middleware |
| **Per-Endpoint (LLM)** | `process_collection`, `generate_report` | 30 req/min | 60s | 🟡 Soft (queue) | LLM service wrapper |
| **Per-Endpoint (Collection)** | `collect_sources` | 10 req/min | 60s | 🟡 Soft (queue) | Collection service |
| **Per-Endpoint (Delivery)** | `send_to_enduser` | 60 req/min | 60s | 🔴 Hard | Delivery service |
| **Per-IP (DDoS)** | Single source IP | 300 req/min | 60s | 🔴 Hard | API gateway |

### 3.4 Rate Limit Response

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 45
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1753645200
Content-Type: application/json

{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please retry after 45 seconds.",
  "limit": 100,
  "remaining": 0,
  "reset_at": "2026-07-27T10:20:00Z",
  "retry_after_seconds": 45
}
```

**Required response headers:**

| Header | Description | Example |
|--------|-------------|---------|
| `X-RateLimit-Limit` | Max requests in window | `100` |
| `X-RateLimit-Remaining` | Remaining in current window | `0` |
| `X-RateLimit-Reset` | Unix timestamp when window resets | `1753645200` |
| `Retry-After` | Seconds until next request allowed | `45` |

### 3.5 Backpressure Strategy

For endpoints that accept queuing (LLM extraction, collection), rate limiting uses a tiered approach:

```
Request arrives
        │
        ▼
  ┌─ Rate check ─┐
  │ Within limit? │──Yes──▶ Process immediately
  └──────┬────────┘
         │ No
         ▼
  ┌─ Queue check ─┐
  │ Below queue   │──Yes──▶ Enqueue with position N
  │ depth limit?  │          → 202 Accepted
  └──────┬────────┘          → Location: /queue/{job_id}
         │ No
         ▼
   429 Rejected
   (queue full)
```

**Queue limits:**

| Queue | Max Depth | Max Wait | Strategy on Full |
|-------|:---:|:---:|------------------|
| LLM Extraction | 500 | 300s (5 min) | Reject 429 — retry with exponential backoff |
| Collection | 100 | 600s (10 min) | Reject 429 — cron retries on next schedule |
| Delivery | 1000 | 120s (2 min) | Queue to overflow channel (email fallback) |

### 3.6 DDoS Protection Basics

| Layer | Mechanism | V1? | Notes |
|-------|-----------|:---:|-------|
| **IP-based** | Per-IP rate limit at FastAPI middleware | ✅ | Default 300 req/min per IP; configurable |
| **Geographic** | Geo-IP block/allow list | ❌ v2 | Optional per-tenant settings |
| **Request size** | Max request body size (16MB default) | ✅ | FastAPI/Starlette built-in |
| **Slowloris** | Request timeout (30s default, configurable) | ✅ | uvicorn timeout settings |
| **Auth brute-force** | 5 failed login attempts → 15-min lockout per IP | ✅ | Implemented in NativeProvider |
| **WAF** | Web application firewall (Cloudflare/modsecurity) | ❌ v3 | External infrastructure |

---

## §4: Admin Dashboard

> Cross-ref: [CD-005 (Admin Dashboard)](../cross-dimensional-catalog.md#cd-005-admin-dashboard),
> [CD-013 (Live Operations Dashboard)](../cross-dimensional-catalog.md#cd-013-live-operations-dashboard).

### 4.1 Current Reality (Gap Description)

```code_evidence
# src/autoinfo/api/server.py — FastAPI app:
#   GET /dashboard → Bootstrap 5 HTML page
#   Shows: collection stats table, KB search box, source health list
#   Does NOT show: user management, billing, operations monitoring, tenant management
#   No admin routes, no admin auth, no RBAC
# Evidence: grep "admin\|dashboard" src/autoinfo/api/server.py returns
#           only the read-only /dashboard route — no admin CRUD
```

### 4.2 Admin Console Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Admin Dashboard                           │
│                    (FastAPI + Jinja2 + HTMX)                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Auth Gate: Admin session required (role=admin)       │   │
│  │  Routes prefixed: /admin/*                            │  │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Users    │ │ System   │ │ Billing  │ │ Collection│       │
│  │ Management│ │ Monitor  │ │ Overview │ │ & Delivery│       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Data Sources:                                         │  │
│  │  - MCP tools (diagnose_system, get_metrics, etc.)     │  │
│  │  - REST API endpoints (already built)                  │  │
│  │  - Prometheus metrics endpoint                         │  │
│  │  - SQLite direct read (admin-only)                     │  │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Technology stack:**

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Web framework** | FastAPI (already in use) | Zero new dependency. Admin routes are a new router. |
| **Template engine** | Jinja2 (already in use) | Matches existing output generation and Web UI dashboard. |
| **Interactivity** | HTMX (lightweight, ~14KB) | AJAX partial updates without SPA framework. Progressive enhancement. |
| **CSS** | Bootstrap 5 (already in use) | Consistent with existing Web UI dashboard. |
| **Charts** | Chart.js (CDN, ~60KB) | Time-series charts for metrics. Lightweight, no build step. |
| **Auth** | Session cookie (same as end-user) | Admin role flag on UserSession. No separate auth system. |

### 4.3 Admin Dashboard Views

#### 4.3.1 User Management (`/admin/users`)

| Feature | Description |
|---------|-------------|
| **User list** | Paginated table: name, email, tenant, status, subscription tier, created date, last active |
| **Search/Filter** | By name, email, tenant, status (trial/active/suspended/cancelled) |
| **User detail** | Full profile: identity anchor, delivery preferences, subscription details, delivery log |
| **Actions** | Suspend user, reactivate user, delete user (GDPR export first), reset password (native auth), revoke all sessions |
| **Bulk operations** | Select multiple → suspend/delete/export data |

```
┌──────────────────────────────────────────────────────────┐
│  Admin / Users                                   [Logout] │
├──────────────────────────────────────────────────────────┤
│  Search: [____________]  Tenant: [All ▾]  Status: [All ▾]│
│                                                          │
│  ┌──────────────────────────────────────────────────────┐│
│  │ ☐ │ Name    │ Email          │ Tenant    │ Status   ││
│  │───│─────────│────────────────│───────────│──────────││
│  │ ☐ │ Alice   │ a@acme.com     │ acme-corp │ Active   ││
│  │ ☐ │ Bob     │ b@beta.com     │ beta-co   │ Trial    ││
│  │ ☐ │ Carol   │ c@gamma.com    │ gamma-ltd │ Suspended││
│  │ ☐ │ ...     │ ...            │ ...       │ ...      ││
│  └──────────────────────────────────────────────────────┘│
│                                                          │
│  [Suspend Selected] [Delete Selected] [Export Data]      │
│  ← Prev   Page 1 of 5   Next →                          │
└──────────────────────────────────────────────────────────┘
```

#### 4.3.2 System Monitoring (`/admin/system`)

| Panel | Data Source | Refresh | Description |
|-------|------------|:---:|-------------|
| **Health score** | `diagnose_system()` MCP tool | 30s | Composite health (0-100), status indicator (🟢/🟡/🔴) |
| **Active collections** | `list_active_collections()` | 10s | Running collection jobs with progress bars |
| **Active deliveries** | `list_active_deliveries()` | 10s | Pending delivery queue depth per channel |
| **Error rate (24h)** | `get_metrics()` MCP tool | 60s | Line chart: errors/min over last 24h |
| **Latency p95/p99** | Prometheus metrics | 60s | Bar chart: p50/p95/p99 per endpoint |
| **LLM usage** | Cost log aggregation | 300s | Tokens consumed today, by model, cost estimate |
| **Disk usage** | `diagnose_system()` | 300s | SQLite DB size, collection cache size, log size |
| **Cron status** | `list_schedules()` | 60s | Last run, next run, success/failure per cron job |
| **Source health** | `get_source_health()` per source | 300s | Table: source name, type, last success, error rate, status |

#### 4.3.3 Billing Overview (`/admin/billing`)

| Panel | Description |
|-------|-------------|
| **MRR (Monthly Recurring Revenue)** | Sum of active subscriptions × price_monthly. Sparkline chart. |
| **Active subscriptions** | Count by plan (free, pro, enterprise). Pie chart. |
| **Trial conversions** | Trial → active conversion rate (last 30 days). Funnel chart. |
| **Churn rate** | Cancellations / total active (monthly). Trend line. |
| **Revenue by tenant** | Top 10 tenants by revenue. Bar chart. |
| **Failed payments** | Recent Stripe payment failures. Table with retry status. |
| **Usage by tenant** | LLM tokens, API calls, storage per tenant. Sortable table. |

#### 4.3.4 Collection & Delivery (`/admin/pipeline`)

| Panel | Description |
|-------|-------------|
| **Collection timeline** | Gantt-style timeline of recent/future collections per domain |
| **Processing queue** | Items waiting in LLM extraction queue. Queue depth chart. |
| **Quality gate stats** | Pass/fail/retry counts per gate (G0-G5). Last 24h. |
| **Delivery status** | Products generated, delivered, failed per channel. Stacked bar chart. |
| **Delivery SLA** | Percentage meeting SLA targets (P0 ≤5min, P1 ≤30min, P2 ≤2hr). |
| **Content freshness** | Domain decay grades (Green/Yellow/Red). Per-domain table. |

### 4.4 Admin Auth & RBAC

Admin access is controlled via user role on `UserSession`:

| Role | Access | Default for |
|------|--------|-------------|
| `admin` | All admin dashboard views, all tenant operations, system configuration | Operator who created the tenant |
| `editor` | KB management, collection configuration, delivery management | Domain expert managing content |
| `viewer` | Read-only access to dashboards (no actions) | Stakeholder monitoring |

**Admin session requirements:**

- Admin sessions have a shorter TTL: 4 hours (vs 24h for end users)
- 2FA (TOTP) enforced for admin role (v2: TOTP, v1: optional)
- All admin actions logged to immutable audit log
- Concurrent admin session limit: 3 (oldest evicted on 4th)

### 4.5 Admin Dashboard MCP Tools (Proposed)

| Tool | Description |
|------|-------------|
| `get_admin_stats(tenant=None)` | Aggregated admin statistics (users, collections, delivery, costs) |
| `list_admin_users(tenant, status, page)` | Paginated user list with filters |
| `suspend_user(user_id, reason)` | Suspend a user (admin override) |
| `get_system_health_dashboard()` | All health metrics in one call (for dashboard rendering) |
| `get_billing_overview(tenant, period)` | MRR, subscriptions, trial conversions, churn |
| `get_pipeline_overview(domain)` | Collection, processing, delivery pipeline status |

---

## §5: Implementation Roadmap

### 5.1 Dependency Graph

```
Phase 1: Tenant Model (CD-001, CD-042)
    │
    ├── Tenant table + TenantContext middleware
    ├── tenant_id column on all existing tables
    └── MCP tools: create_tenant, get_tenant, list_tenants
         │
         ▼
Phase 2: Auth (CD-002, CD-021)
    │
    ├── UserSession model + session middleware
    ├── NativeProvider (email + bcrypt)
    ├── MagicLinkProvider (email one-time links)
    ├── API Key generation + validation
    ├── Identity anchor enforcement on UserProfile
    └── MCP tools: create_api_key, revoke_api_key
         │
         ▼
Phase 3: Rate Limiting (CD-003)
    │
    ├── SlidingWindow middleware
    ├── Per-tenant, per-user, per-endpoint limits
    ├── 429 response with standard headers
    └── Queue-based backpressure for LLM + collection
         │
         ▼
Phase 4: Admin Dashboard (CD-005, CD-013)
    │
    ├── /admin/* FastAPI routes
    ├── User management views
    ├── System monitoring dashboard
    ├── Billing overview
    ├── Collection/delivery pipeline views
    └── Admin RBAC (admin/editor/viewer roles)
```

### 5.2 Effort Estimate

| Phase | Scope | Effort | Dependencies |
|-------|-------|:---:|--------------|
| **Phase 1: Tenant Model** | Tenant table, context middleware, tenant_id migration, MCP tools | 5–7 days | None (greenfield) |
| **Phase 2: Auth** | Session management, native/magic-link providers, API keys, identity anchors | 7–10 days | Phase 1 (TenantContext) |
| **Phase 3: Rate Limiting** | Sliding window middleware, tiered limits, queue backpressure | 3–5 days | Phase 2 (user/API-key identity) |
| **Phase 4: Admin Dashboard** | 4 dashboard views, HTMX interactivity, Chart.js, admin RBAC | 7–10 days | Phase 2 (admin sessions), Phase 1 (tenant scoping) |
| **Total** | | **22–32 days** | |

### 5.3 Priority Relative to Other Gaps

Per [cross-dimensional-catalog.md §4](../cross-dimensional-catalog.md#section-4-priority-fix-matrix):

- CD-001 (Multi-Tenancy): **P1 🟡** — critical if onboarding multi-tenant customers
- CD-002 (Auth): **P1 🟡** — required for any self-service end-user experience
- CD-003 (Rate Limiting): **P1 🟡** — required for production deployment with external API access
- CD-005 (Admin Dashboard): **P2 🟢** — important for operations but not blocking
- CD-013 (Live Ops Dashboard): **P2 🟢** — superset of CD-005; combined in Phase 4
- CD-021 (Identity Anchor): **P2 🟢** — spec exists in delivery.md; implementation coupled with Auth (Phase 2)
- CD-042 (Multi-Tenant DB Isolation): **P3 ⚪** — depends on CD-001; database-per-tenant is a v2+ scaling concern

---

## Cross-Reference Index

| Gap ID | This Spec Section | External Reference |
|--------|:---:|---|
| CD-001 | §1 (Multi-Tenancy Model) | [cross-dimensional-catalog.md §CD-001](../cross-dimensional-catalog.md#cd-001-multi-tenancy-isolation) |
| CD-002 | §2 (End-User Authentication) | [cross-dimensional-catalog.md §CD-002](../cross-dimensional-catalog.md#cd-002-end-user-authentication) |
| CD-003 | §3 (Rate Limiting) | [cross-dimensional-catalog.md §CD-003](../cross-dimensional-catalog.md#cd-003-rate-limiting--abuse-prevention) |
| CD-005 | §4 (Admin Dashboard) | [cross-dimensional-catalog.md §CD-005](../cross-dimensional-catalog.md#cd-005-admin-dashboard) |
| CD-013 | §4.3.2 (System Monitoring) | [cross-dimensional-catalog.md §CD-013](../cross-dimensional-catalog.md#cd-013-live-operations-dashboard) |
| CD-021 | §2.5 (Identity Anchor) | [delivery.md §4.3](./delivery.md#43-identity-anchors) |
| CD-042 | §1 (Tenant Isolation) | [cross-dimensional-catalog.md §CD-042](../cross-dimensional-catalog.md#cd-042-no-multi-tenant-data-isolation) |
| — | Data models: Tenant, ApiKey, UserSession, RateLimit | [data-models.md §6](./data-models.md#6-auth--multi-tenancy-models) |
| — | End user lifecycle, identity anchors, subscription models | [delivery.md §4](./delivery.md#4-end-user-lifecycle) |
| — | Cost metering, audit logging, observability (admin dashboard data sources) | [operations.md](./operations.md) |

---

*End of document. All content is architectural specification for systems that do not yet exist in the AutoInfo codebase.*
