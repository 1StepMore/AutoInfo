# End User Onboarding & Operations Guide

**Purpose**: Spec for how End Users (paying customers) are provisioned, receive
products, manage preferences, and interact with AutoInfo. This is the operator
reference — the agent or human operator follows this to manage End User lifecycle.

References: F36-F40 in `expectations.md`, `delivery.md` §4-5.

## End User Identity Model

- **End User** = Paying Customer (single person). No distinction between
  "consumer" and "payer" — the subscriber pays for and consumes the product.
- Each End User has a `user_id` (UUID), profile, and one or more subscriptions.
- Identity anchors are channel-specific: `telegram_id`, `wechat_oa_openid`,
  `wechat_work_userid`, `dingtalk_userid`, `discord_userid`, plus mandatory `email`.

## Provisioning Flow

### Step 1: Operator Creates End User

The operator (agent or human Director User) creates the End User profile:

```
create_end_user(
    name="Acme Corp",
    email="admin@acme.com",
    tier="pro",
    delivery_preferences={
        "channels": ["email", "telegram"],
        "quiet_hours": {
            "start": "22:00",
            "end": "07:00",
            "timezone": "Asia/Shanghai"
        }
    },
    required_domains=["medical-research", "ai-commercial"]
)
```

**Validation rules:**
- At least one delivery channel must be configured (email is mandatory fallback)
- At least one domain must be subscribed
- Email is always required

### Step 2: Welcome & Activation

On creation (status: `trial`), the system automatically:
1. Sends a welcome message via all configured channels
2. Provides a self-service portal access link (magic-link via email)
3. Starts trial period (default: 14 days, configurable)

The operator can extend trial per End User via `update_end_user`.

### Step 3: Product Delivery Starts

Based on the End User's subscribed domains and delivery preferences,
products begin flowing:

| Product Type | Examples | Delivery Cadence |
|-------------|----------|-----------------|
| **RAW** | API data feeds, webhook streams, bulk exports | On-demand / scheduled pull |
| **PROCESSED** | Scheduled digests, thematic reports, alert streams | Push: daily/weekly digest, real-time alerts |

**Product-to-channel routing** (configurable per subscription):
- Short alerts → Telegram / WeChat Work / DingTalk (instant)
- Daily digests → Email + optional push channel
- Weekly reports → Email (primary) + optional secondary channel

## Subscription Lifecycle

```
                    ┌──────────┐
                    │  TRIAL   │  (default: 14 days)
                    └────┬─────┘
                         │ payment confirmed
                    ┌────▼─────┐
                    │  ACTIVE  │
                    └────┬─────┘
                    ┌────┴──────┐
                    │           │
              ┌─────▼──┐  ┌────▼────────┐
              │SUSPENDED│  │  CANCELLED  │  (explicit)
              │(payment │  └────┬────────┘
              │ failed) │       │
              └────┬─────┘      │ re-activate within 90 days
                   │            │ → full history restored
              payment resolved  │
                   │            │ after 90 days → archived
              ┌────▼─────┐      │ (data retained per GDPR)
              │  ACTIVE  │      │
              └──────────┘      │
                          ┌─────▼─────────┐
                          │ PROFILE ARCHIVED │
                          └─────────────────┘
```

### State Details

| State | Duration | Product Delivery | End User Can | Operator Actions |
|-------|----------|-----------------|--------------|-----------------|
| **Trial** | Configurable (default 14d) | ✅ Full access, watermarked outputs | View portal, manage preferences | Extend trial, convert to active |
| **Active** | Indefinite | ✅ Full access | All portal functions | Upgrade/downgrade tier, update preferences |
| **Suspended** | 7-day grace period | ✅ Continues during grace | Limited portal (billing only) | Re-activate (payment resolved), cancel (grace expired) |
| **Cancelled** | Immediate | ❌ Stopped | Archive access (90d) | Re-activate (within 90d) |
| **Archived** | Permanent (after 90d cancelled) | ❌ N/A | ❌ No access | Restore (data retained per GDPR) |

### Grace Period & Suspension

1. Payment fails → status changes to `suspended`, grace period starts (7 days)
2. Alerts sent to End User on day 1, 3, 7 of grace period
3. Products continue delivery during grace
4. If payment resolved → status returns to `active`, confirmation sent
5. If grace expires → status changes to `cancelled`, all deliveries stop
6. Goodbye message sent with re-activation link

## Self-Service Portal

The portal is available via the CLI (v1 implementation — web UI planned).

### End User Can:

| Action | Portal Command / UI |
|--------|-------------------|
| View profile | `autoinfo portal profile` |
| Update delivery preferences | `autoinfo portal preferences` |
| Toggle channels on/off | `autoinfo portal preferences --channels email,telegram` |
| View subscription status | `autoinfo portal status` |
| Browse delivery history | `autoinfo portal history` |
| Download past products | `autoinfo portal archive` |
| View cost/usage | `autoinfo portal cost` |
| Set quiet hours | `autoinfo portal preferences --quiet-hours "22:00-07:00"` |

### Authentication

- Email-based magic link (no password)
- Link expires in 15 minutes
- Session token valid for 7 days
- Optional social login: WeChat OAuth, Telegram OAuth

## Delivery Channels

| Channel | Capability | Rate Limit | Fallback Priority |
|---------|-----------|------------|-------------------|
| **Email** (mandatory) | Rich HTML, plain text, PDF attachments | N/A | 1 (last resort) |
| **Telegram** | Markdown, inline buttons, file uploads | 30 msg/s per bot | 2 |
| **WeChat OA** | Rich article (图文消息), template message | Unlimited | 3 |
| **WeChat Work** | Markdown, file upload, interactive card | Unlimited | 4 |
| **DingTalk** | Markdown, action card, feed card | Unlimited | 5 |
| **Discord** | Embed, file attachment, slash command | 5 msg/s per webhook | 6 |

### Quiet Hours

End Users can configure quiet hours (e.g., 22:00-08:00) during which
non-critical products are queued and delivered after quiet hours end.
Alerts and critical notifications bypass quiet hours.

## Data Privacy & Retention

| Aspect | Policy |
|--------|--------|
| **Soft-delete** | End User profiles are soft-deleted on cancellation; restorable within 90 days |
| **Permanent purge** | Only Director User (human) can purge with `--purge` flag |
| **GDPR export** | Full data export available via `export_user_data(user_id)` MCP tool |
| **Retention** | Profile data retained for 90 days after cancellation (archived state), then auto-cleaned |
| **Audit trail** | All operator actions on End User records logged with `updated_by` field |

## Agent Overrides

The operator (agent) can:
- Update any profile field or subscription state (with audit trail: `updated_by: agent`)
- Extend trial periods
- Suspend or cancel subscriptions
- Soft-delete entries on behalf of End User

The operator (agent) **cannot**:
- Permanently purge End User data (Director User only)
- Delete End User profiles (deactivate only)
- Access End User portal without authorization

## References

- `docs/dev/specs/expectations.md` — F36-F40 (End User lifecycle specs)
- `docs/dev/specs/delivery.md` §4 — End User lifecycle data models
- `docs/dev/specs/delivery.md` §5 — Product lifecycle & delivery
- `docs/dev/specs/operations.md` §2 — Data privacy & retention
- `docs/dev/user-authorization-matrix.md` — Authorization boundaries
- `docs/dev/end-user-sla.md` — Delivery SLA targets & tracking
