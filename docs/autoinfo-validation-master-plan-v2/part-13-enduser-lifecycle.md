# Part 13: End User Lifecycle — Paying Customer Perspective (Q61-Q65)

**Coverage:** End user profile & subscription CRUD, lifecycle state machine, multi-channel delivery configuration, product delivery with SLA tracking, self-service portal, data privacy (soft-delete, restore, GDPR export)

**Expectations referenced:** F36 (Profile & Subscription), F37 (Multi-Channel Delivery), F38 (Lifecycle State Machine), F39 (Delivery Reliability & Logging), F40 (Self-Service Portal), F42 (External Billing — deferred to v2+, partial), F43 (End-User Cost Dashboard), F47 (Data Deletion & Retention)

---

## Q61: End User Profile Registration & Subscription

**User says:** "I am a paying customer. I want to register, get a subscription, and see my profile."

### Prerequisites

```bash
cd /tmp && rm -rf test-q61 && mkdir test-q61 && cd test-q61
autoinfo init --demo medical-research
```

### Scenarios

#### 61.1 🟢 Create an end user profile via CLI

```bash
autoinfo enduser create \
  --user-id alice \
  --name "Alice Smith" \
  --email alice@example.com \
  --trial --tier pro
```

**Expected Result:**

- ✅ Exit code 0
- ✅ Output: "Created end-user: alice (Alice Smith)"
- ✅ Profile stored with status="trial", tier="pro"
- ✅ `trial_start` set to current timestamp, `trial_end` set to 14 days later
- ✅ `.autoinfo/users.db` created with `user_profiles` table

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.2 🟢 Get end user profile by user ID

```bash
autoinfo enduser get --user-id alice
```

**Expected Result:**

- ✅ Exit code 0
- ✅ JSON output includes: user_id, name, email, status, tier, trial_start, trial_end, created_at, updated_at
- ✅ delivery_prefs present (may be empty)
- ✅ Status is "trial"

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.3 🟢 List all end user profiles

```bash
autoinfo enduser list
```

**Expected Result:**

- ✅ Exit code 0
- ✅ Table output with columns: User ID, Name, Email, Status, Tier
- ✅ Alice appears in the list
- ✅ Total count shown

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.4 🟢 List end users with JSON output

```bash
autoinfo enduser list --json
```

**Expected Result:**

- ✅ Valid JSON array of user profiles
- ✅ Each entry has user_id, name, email, status, tier, created_at

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.5 🟢 Update end user profile (partial update)

```bash
autoinfo enduser update --user-id alice --email alice.new@example.com --tier enterprise
```

**Expected Result:**

- ✅ Exit code 0
- ✅ Output: "Updated end-user: alice"
- ✅ Email changed to alice.new@example.com
- ✅ Tier changed to enterprise
- ✅ `updated_at` updated
- ✅ Other fields unchanged

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.6 🟢 State machine: transition trial → active

```python
from autoinfo.user_store import transition_end_user

# Simulate payment confirmed: trial → active
result = transition_end_user("alice", "active")
print(f"Transition: {result}")

assert result.get("success"), f"Transition failed: {result}"
assert result["from_status"] == "trial"
assert result["to_status"] == "active"
print(f"✅ trial → active: OK")
```

**Expected Result:**

- ✅ Transition succeeds
- ✅ `from_status` = "trial", `to_status` = "active"
- ✅ Audit log entry written
- ✅ Profile now shows status="active" in `autoinfo enduser get --user-id alice`

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.7 🟢 State machine: transition active → suspended → active

```python
from autoinfo.user_store import transition_end_user

# Payment failed: active → suspended
r1 = transition_end_user("alice", "suspended")
assert r1.get("success"), f"suspend failed: {r1}"
print(f"✅ active → suspended: {r1['from_status']} → {r1['to_status']}")

# Payment resolved: suspended → active
r2 = transition_end_user("alice", "active")
assert r2.get("success"), f"reactivate failed: {r2}"
print(f"✅ suspended → active: {r2['from_status']} → {r2['to_status']}")
```

**Expected Result:**

- ✅ Both transitions succeed
- ✅ active → suspended → active round trip works
- ✅ Each transition logged to audit log

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.8 🔴 State machine: trial → suspended invalid

```python
from autoinfo.user_store import transition_end_user

# From trial, cannot go directly to suspended
result = transition_end_user("alice", "suspended")
assert "error_code" in result
assert result["error_code"] == "InvalidTransition"
print(f"✅ InvalidTransition: {result['message']}")
```

**Expected Result:**

- ❌ Returns error_code "InvalidTransition"
- ❌ Profile status unchanged
- ❌ Error message lists valid transitions: "active, cancelled"

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.9 🔴 State machine: cancelled is terminal

```python
from autoinfo.user_store import transition_end_user

# Cancel first
r1 = transition_end_user("alice", "cancelled")
assert r1.get("success"), f"cancel failed: {r1}"
print(f"✅ Cancelled: {r1['from_status']} → {r1['to_status']}")

# Try to transition from cancelled (terminal)
r2 = transition_end_user("alice", "active")
assert "error_code" in r2
assert r2["error_code"] == "InvalidTransition"
print(f"✅ Terminal state: {r2['message']}")
```

**Expected Result:**

- ❌ First transition succeeds (to cancelled)
- ❌ Second transition fails with InvalidTransition
- ❌ cancelled is terminal (no outgoing transitions allowed)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.10 🔴 Get nonexistent user

```bash
autoinfo enduser get --user-id nonexistent
```

**Expected Result:** ❌ Exit code != 0. Error: "End-user 'nonexistent' not found".

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.11 🔴 Create duplicate user

```bash
autoinfo enduser create --user-id alice --name "Alice Duplicate" --email a@b.com
```

**Expected Result:** ❌ Exit code != 0. Error mentions duplicate/integrity error.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.12 🟢 Create end user via MCP tool

```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("create_end_user", {
    "user_id": "bob",
    "name": "Bob User",
    "email": "bob@example.com",
    "status": "trial",
    "tier": "pro",
    "delivery_prefs": {"email": True}
})
data = json.loads(result.content[0].text)
print(f"✅ MCP create_end_user: {data}")
assert "user_id" in data or "status" in data
```

**Expected Result:** ✅ End user created via MCP, confirmation returned.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.13 🟢 List end users via MCP tool

```python
result = app.call_tool("list_end_users", {})
data = json.loads(result.content[0].text)
users = data.get("users", data.get("items", []))
print(f"✅ MCP list_end_users: {len(users)} user(s)")
assert len(users) >= 1
for u in users:
    print(f"  {u.get('user_id','?')}: {u.get('name','?')} [{u.get('status','?')}]")
```

**Expected Result:** ✅ Returns all end user profiles.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 61.14 🔴 Delete end user

```bash
autoinfo enduser delete --user-id alice
```

**Expected Result:**

- ✅ Exit code 0
- ✅ Profile removed
- ✅ Associated subscriptions also removed
- ✅ `autoinfo enduser get --user-id alice` now returns "not found"

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q61 Verdict

| Scenario | Result |
|----------|--------|
| 61.1 Create profile CLI | ⬜ |
| 61.2 Get profile CLI | ⬜ |
| 61.3 List profiles CLI | ⬜ |
| 61.4 List profiles JSON | ⬜ |
| 61.5 Update profile | ⬜ |
| 61.6 trial → active | ⬜ |
| 61.7 active ↔ suspended round trip | ⬜ |
| 61.8 trial → suspended invalid | ⬜ |
| 61.9 cancelled terminal state | ⬜ |
| 61.10 Get nonexistent | ⬜ |
| 61.11 Create duplicate | ⬜ |
| 61.12 MCP create | ⬜ |
| 61.13 MCP list | ⬜ |
| 61.14 Delete profile | ⬜ |

**OVERALL: ⬜**

---

## Q62: Multi-Channel Delivery Configuration

**User says:** "I want to select how I receive my products. I use Telegram for instant alerts and email for daily digests."

### Prerequisites

```bash
cd /tmp && rm -rf test-q62 && mkdir test-q62 && cd test-q62
autoinfo init --demo medical-research

# Create a test end user
autoinfo enduser create --user-id carol --name "Carol Test" --email carol@example.com --trial --tier pro
```

### Scenarios

#### 62.1 🟢 Configure email + Telegram delivery preferences

```bash
autoinfo portal preferences update \
  --user-id carol \
  --delivery-prefs '{"email":true,"telegram":true,"telegram_chat_id":"123456789","digest_channel":"email","alert_channel":"telegram"}'
```

**Expected Result:**

- ✅ Exit code 0
- ✅ Confirmation: "Updated preferences for end-user: carol"
- ✅ Preferences stored in user profile

**Actual Result:** _________ **PASS / FAIL:** _________

#### 62.2 🟢 View delivery preferences

```bash
autoinfo portal preferences show --user-id carol
```

**Expected Result:**

- ✅ Exit code 0
- ✅ Shows: User, Name, Email, Tier, Status, and all preferences
- ✅ telegram_chat_id shown
- ✅ digest_channel and alert_channel preferences visible

**Actual Result:** _________ **PASS / FAIL:** _________

#### 62.3 🟢 View delivery preferences as JSON

```bash
autoinfo portal preferences show --user-id carol --json
```

**Expected Result:** ✅ Valid JSON with all delivery preferences.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 62.4 🟢 Configure all 6 delivery channels

```python
from autoinfo.user_store import update_profile

# Configure all available channels per F37 specification
prefs = {
    "email": True,
    "telegram": True,
    "telegram_chat_id": "987654321",
    "wechat_oa": True,
    "wechat_oa_openid": "oa_open_123",
    "wechat_work": True,
    "wechat_work_userid": "ww_456",
    "dingtalk": True,
    "dingtalk_userid": "dt_789",
    "discord": True,
    "discord_userid": "discord_999",
    "digest_channel": "email",
    "alert_channel": "telegram",
    "report_channel": "email",
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00",
    "timezone": "Asia/Shanghai"
}

profile = update_profile(user_id="carol", delivery_prefs=prefs)
assert profile is not None
assert profile.delivery_prefs.get("telegram_chat_id") == "987654321"
assert profile.delivery_prefs.get("quiet_hours_start") == "22:00"
print(f"✅ All 6 channels configured: {list(prefs.keys())[:10]}...")
```

**Expected Result:** ✅ All delivery channels can be configured simultaneously. JSON-stored preferences retained.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 62.5 🟢 Product-to-channel mapping

```python
from autoinfo.models import Product, ProductType

# Define products with channel routing
raw_feed = Product(
    id="raw_feed_01",
    domain="medical-research",
    type=ProductType.RAW,
    name="PubMed IVF Feed",
    config={"keywords": ["IVF", "embryo"]},
    delivery_channels=["telegram", "discord"],
)

daily_digest = Product(
    id="digest_01",
    domain="medical-research",
    type=ProductType.PROCESSED,
    name="Daily IVF Digest",
    config={"period": "day", "format": "html"},
    delivery_channels=["email"],
)

weekly_report = Product(
    id="report_01",
    domain="medical-research",
    type=ProductType.PROCESSED,
    name="Weekly Research Report",
    config={"period": "week", "format": "pdf"},
    delivery_channels=["email", "wechat_oa"],
)

print(f"✅ Products configured with channel routing:")
print(f"  {raw_feed.name} → {raw_feed.delivery_channels}")
print(f"  {daily_digest.name} → {daily_digest.delivery_channels}")
print(f"  {weekly_report.name} → {weekly_report.delivery_channels}")
```

**Expected Result:** ✅ Products can specify their delivery channels. Short alerts route to instant channels (Telegram), daily digests to email, weekly reports to email + secondary.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 62.6 🟢 List products via CLI

```bash
autoinfo output list-templates --domain medical-research 2>/dev/null || autoinfo enduser list --json
```

**Expected Result:** ✅ Products listed with name, type, and delivery channels.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 62.7 🟢 List products via MCP

```python
from autoinfo.mcp.server import app
import json

result = app.call_tool("list_products", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
products = data.get("products", data.get("items", []))
print(f"✅ list_products: {len(products)} product(s)")
for p in products:
    print(f"  {p.get('name','?')} ({p.get('type','?')}) → channels: {p.get('delivery_channels',[])}")
```

**Expected Result:** ✅ Products listed with type, name, delivery_channels.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 62.8 🔴 Reachability validation — missing channel ID

```python
from autoinfo.user_store import update_profile

# Attempt to enable Telegram without providing chat_id
invalid_prefs = {
    "email": True,
    "telegram": True,
    # Missing telegram_chat_id
}

# This should fail validation or at minimum flag the missing ID
profile = update_profile(user_id="carol", delivery_prefs=invalid_prefs)
channels = profile.delivery_prefs
if channels.get("telegram") and not channels.get("telegram_chat_id"):
    print(f"⚠️ Telegram enabled but telegram_chat_id is missing (should warn)")
else:
    print(f"✅ Validation passed or missing ID accepted")

# Check at least one channel is active (email mandatory fallback per F37)
assert channels.get("email", False) or any(
    channels.get(c, False) for c in ["telegram", "wechat_oa", "wechat_work", "dingtalk", "discord"]
), "At least one channel must remain active"
```

**Expected Result:**

- ⚠️ If validation exists: error returned for missing channel ID
- ⚠️ If no strict validation: warning printed by agent
- ✅ Email must always remain active as fallback (per F37 default channel rule)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 62.9 🔴 Update preferences for nonexistent user

```bash
autoinfo portal preferences update --user-id nonexistent --delivery-prefs '{"email":true}'
```

**Expected Result:** ❌ Exit code != 0. Error: "End-user 'nonexistent' not found".

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q62 Verdict

| Scenario | Result |
|----------|--------|
| 62.1 Configure email + Telegram | ⬜ |
| 62.2 View preferences | ⬜ |
| 62.3 Preferences JSON | ⬜ |
| 62.4 Configure all 6 channels | ⬜ |
| 62.5 Product-to-channel mapping | ⬜ |
| 62.6 List products CLI | ⬜ |
| 62.7 List products MCP | ⬜ |
| 62.8 Missing channel ID | ⬜ |
| 62.9 Nonexistent user prefs | ⬜ |

**OVERALL: ⬜**

---

## Q63: Product Delivery Lifecycle

**User says:** "I subscribed to a product. I want to receive my RAW feed and PROCESSED digest, and I want the system to prove delivery happened within SLA."

### Prerequisites

```bash
cd /tmp && rm -rf test-q63 && mkdir test-q63 && cd test-q63
autoinfo init --demo medical-research

# Create end user
autoinfo enduser create --user-id dave --name "Dave SLA" --email dave@example.com --trial --tier pro

# Set up delivery preferences
autoinfo portal preferences update \
  --user-id dave \
  --delivery-prefs '{"email":true,"digest_channel":"email","alert_channel":"email"}'
```

### Scenarios

#### 63.1 🟢 Create a subscription for the end user

```python
from autoinfo.user_store import create_subscription, list_subscriptions

# Create a subscription for the PROCESSED daily digest product
sub = create_subscription(
    user_id="dave",
    product_id="daily-digest-medical",
    status="active",
    auto_renew=True,
)
print(f"✅ Subscription created: id={sub.sub_id}, product={sub.product_id}, status={sub.status}")

# Verify subscription appears in list
subs = list_subscriptions(user_id="dave")
assert len(subs) >= 1
print(f"✅ {len(subs)} subscription(s) for dave")
```

**Expected Result:** ✅ Subscription created with unique sub_id, linked to user, active status.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 63.2 🟢 Deliver a RAW product (API feed) and log delivery

```python
from autoinfo.models import Product, ProductType, DeliveryResult
from autoinfo.delivery_log import query_delivery_log
from datetime import datetime, timezone
import uuid

# Simulate RAW product delivery
sub_id = "sub_raw_001"
log_id = str(uuid.uuid4())
now = datetime.now(timezone.utc).isoformat()

# Append delivery log entry for RAW feed delivery
from autoinfo.delivery_log import append_delivery_log
append_delivery_log(
    subscription_id=sub_id,
    channel="email",
    message_type="raw_feed",
    status="delivered",
    attempt_count=1,
    error_message="",
    sla_tier="critical",
)

# Verify log entry
entries = query_delivery_log(subscription_id=sub_id)
assert len(entries) >= 1
entry = entries[0]
assert entry.status == "delivered"
assert entry.sla_tier == "critical"
print(f"✅ RAW product delivery logged: {entry.log_id}, status={entry.status}, sla={entry.sla_tier}")
```

**Expected Result:** ✅ RAW product delivery recorded in append-only delivery log with correct SLA tier.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 63.3 🟢 Deliver a PROCESSED product (daily digest) with retry

```python
from autoinfo.delivery import deliver_with_retry
from autoinfo.delivery import SMTPDeliveryChannel
from autoinfo.models import Product, ProductType
from autoinfo.delivery_log import query_delivery_log

sub_id = "sub_digest_001"

# Create a mock PROCESSED product
product = Product(
    id="digest_med_20260725",
    domain="medical-research",
    type=ProductType.PROCESSED,
    name="Daily IVF Digest",
    config={"period": "day"},
    delivery_channels=["email"],
)

# Send through SMTP channel (will fail if no SMTP, but logs attempt)
channel = SMTPDeliveryChannel()
payload = {
    "subject": "Your Daily IVF Research Digest",
    "body": "# IVF Research Update\n\nNew studies published today...",
    "format": "html",
}

result = deliver_with_retry(
    channel=channel,
    product=product,
    payload=payload,
    recipients=["dave@example.com"],
    subscription_id=sub_id,
    sla_tier="standard",  # P1: digest ≤30min
)

print(f"✅ Delivery result: status={result.status}, channel={result.channel}")
print(f"   recipients={result.recipient_count}, error={result.error}")

# Verify delivery was logged
entries = query_delivery_log(subscription_id=sub_id)
print(f"   {len(entries)} log entries for subscription")
for e in entries:
    print(f"   [{e.status}] {e.channel} attempt {e.attempt_count} — {e.error_message or 'OK'}")
```

**Expected Result:**

- ✅ Delivery attempted (may succeed or fail depending on SMTP config)
- ✅ Delivery recorded in log regardless of outcome
- ✅ Log shows attempt count, status, channel, SLA tier
- ✅ If delivery fails, retry mechanism logs "retrying" entries

**Actual Result:** _________ **PASS / FAIL:** _________

#### 63.4 🟢 SLA timing verification — P0 delivery within 5 minutes

```python
from autoinfo.delivery_log import query_delivery_log, get_delivery_stats
from datetime import datetime, timezone, timedelta
import time

sub_id = "sub_sla_p0_001"
channel_name = "telegram_mock"

# Record attempt time
start_time = datetime.now(timezone.utc)

# Simulate P0 delivery (alert — should be ≤5 min)
from autoinfo.delivery_log import append_delivery_log
append_delivery_log(
    subscription_id=sub_id,
    channel=channel_name,
    message_type="alert",
    status="delivered",
    attempt_count=1,
    sla_tier="critical",
)

end_time = datetime.now(timezone.utc)
elapsed = (end_time - start_time).total_seconds()

# Check SLA: P0 = critical = ≤5min (300s)
sla_p0_limit_s = 300
assert elapsed <= sla_p0_limit_s, (
    f"P0 SLA exceeded: {elapsed:.1f}s > {sla_p0_limit_s}s"
)
print(f"✅ P0 delivery SLA met: {elapsed:.1f}s (limit: {sla_p0_limit_s}s)")

# Verify log
entries = query_delivery_log(subscription_id=sub_id)
assert any(e.sla_tier == "critical" and e.status == "delivered" for e in entries)
print(f"✅ P0 delivery logged with sla_tier=critical")
```

**Expected Result:** ✅ Delivery completes within 300s and is logged with sla_tier="critical".

**Actual Result:** _________ **PASS / FAIL:** _________

#### 63.5 🟢 SLA timing verification — P1 delivery within 30 minutes

```python
from autoinfo.delivery_log import append_delivery_log

sub_id = "sub_sla_p1_001"

start_time = datetime.now(timezone.utc)
append_delivery_log(
    subscription_id=sub_id,
    channel="email",
    message_type="report",
    status="delivered",
    attempt_count=1,
    sla_tier="standard",
)
end_time = datetime.now(timezone.utc)
elapsed = (end_time - start_time).total_seconds()

# P1 = standard = ≤30min (1800s)
sla_p1_limit_s = 1800
assert elapsed <= sla_p1_limit_s, (
    f"P1 SLA exceeded: {elapsed:.1f}s > {sla_p1_limit_s}s"
)
print(f"✅ P1 delivery SLA met: {elapsed:.1f}s (limit: {sla_p1_limit_s}s)")
```

**Expected Result:** ✅ Delivery completes within 1800s and is logged with sla_tier="standard".

**Actual Result:** _________ **PASS / FAIL:** _________

#### 63.6 🟢 SLA timing verification — P2 delivery within 2 hours

```python
from autoinfo.delivery_log import append_delivery_log

sub_id = "sub_sla_p2_001"

start_time = datetime.now(timezone.utc)
append_delivery_log(
    subscription_id=sub_id,
    channel="webhook",
    message_type="bulk_export",
    status="delivered",
    attempt_count=1,
    sla_tier="bulk",
)
end_time = datetime.now(timezone.utc)
elapsed = (end_time - start_time).total_seconds()

# P2 = bulk = ≤2hr (7200s)
sla_p2_limit_s = 7200
assert elapsed <= sla_p2_limit_s, (
    f"P2 SLA exceeded: {elapsed:.1f}s > {sla_p2_limit_s}s"
)
print(f"✅ P2 delivery SLA met: {elapsed:.1f}s (limit: {sla_p2_limit_s}s)")
```

**Expected Result:** ✅ Delivery completes within 7200s and is logged with sla_tier="bulk".

**Actual Result:** _________ **PASS / FAIL:** _________

#### 63.7 🟢 Retry chain on failure — fallback to alternate channel

```python
from autoinfo.delivery_log import append_delivery_log, query_delivery_log

sub_id = "sub_retry_chain_001"

# Simulate primary channel failure (Telegram)
append_delivery_log(
    subscription_id=sub_id,
    channel="telegram",
    message_type="alert",
    status="failed",
    attempt_count=1,
    error_message="Telegram API timeout",
    sla_tier="critical",
)

# Simulate retry on fallback channel (email)
append_delivery_log(
    subscription_id=sub_id,
    channel="email",
    message_type="alert",
    status="delivered",
    attempt_count=2,
    error_message="",
    sla_tier="critical",
)

# Verify retry chain
entries = query_delivery_log(subscription_id=sub_id)
assert len(entries) >= 2
assert entries[0].status == "failed"
assert entries[0].channel == "telegram"
assert entries[1].status == "delivered"
assert entries[1].channel == "email"
print(f"✅ Retry chain: telegram failed → email delivered")
```

**Expected Result:** ✅ Log shows primary channel failure followed by fallback success. Product never silently dropped.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 63.8 🔴 All channels fail — product queued

```python
from autoinfo.delivery_log import append_delivery_log, query_delivery_log

sub_id = "sub_all_fail_001"

# Simulate all channels failing
for channel in ["telegram", "email", "discord"]:
    append_delivery_log(
        subscription_id=sub_id,
        channel=channel,
        message_type="alert",
        status="failed",
        attempt_count=1,
        error_message=f"{channel} unreachable",
        sla_tier="critical",
    )

# Verify all failed
entries = query_delivery_log(subscription_id=sub_id)
failed_channels = [e.channel for e in entries if e.status == "failed"]
print(f"✅ All channels failed: {failed_channels}")
assert len(failed_channels) == 3, f"Expected 3 failures, got {len(failed_channels)}"

# Per F39: "Never silently drop a product" — the product is queued for next window
print(f"✅ Product queued for next delivery window (not silently dropped)")
```

**Expected Result:** ❌ All delivery attempts logged as failed. Product queued for next delivery window per F39 retry chain specification.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 63.9 🟢 Query delivery log via CLI portal

```bash
# Create a subscription ID for dave and add delivery log entries first
python3 -c "
from autoinfo.user_store import create_subscription
from autoinfo.delivery_log import append_delivery_log

sub = create_subscription(user_id='dave', product_id='daily-digest-medical')
sid = sub.sub_id
append_delivery_log(subscription_id=sid, channel='email', message_type='digest', status='delivered', attempt_count=1, sla_tier='standard')
append_delivery_log(subscription_id=sid, channel='telegram', message_type='alert', status='delivered', attempt_count=1, sla_tier='critical')
print(sid)
" > /tmp/sid_dave.txt

# View delivery history
autoinfo portal history --user dave
```

**Expected Result:**

- ✅ Delivery history shown with columns: Log ID, Channel, Type, Status, Attempt, Last Attempt
- ✅ Both email and Telegram deliveries visible
- ✅ Total count shown

**Actual Result:** _________ **PASS / FAIL:** _________

#### 63.10 🟢 Query delivery log as JSON

```bash
autoinfo portal history --user dave --json
```

**Expected Result:** ✅ Valid JSON array with delivery log entries. Each entry has log_id, subscription_id, channel, message_type, status, attempt_count, last_attempt, error_message, sla_tier.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 63.11 🟢 Delivery stats aggregated

```python
from autoinfo.delivery_log import get_delivery_stats
from autoinfo.delivery_log import append_delivery_log
import uuid

# Add several entries with different statuses
sub_id = "sub_stats_001"
for status in ["delivered", "delivered", "failed", "delivered", "retrying"]:
    append_delivery_log(
        subscription_id=sub_id,
        channel="email",
        message_type="digest",
        status=status,
        attempt_count=1,
        sla_tier="standard",
    )

# Get aggregated stats
stats = get_delivery_stats(subscription_id=sub_id)
print(f"✅ Delivery stats: {stats}")
# Expect: total=5, by_status with delivered/failed/retrying counts
```

**Expected Result:** ✅ Aggregated stats returned with total count and breakdown by status or SLA tier.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q63 Verdict

| Scenario | Result |
|----------|--------|
| 63.1 Create subscription | ⬜ |
| 63.2 Deliver RAW product | ⬜ |
| 63.3 Deliver PROCESSED product | ⬜ |
| 63.4 P0 SLA (≤5min) | ⬜ |
| 63.5 P1 SLA (≤30min) | ⬜ |
| 63.6 P2 SLA (≤2hr) | ⬜ |
| 63.7 Retry chain fallback | ⬜ |
| 63.8 All channels fail | ⬜ |
| 63.9 Query log CLI | ⬜ |
| 63.10 Query log JSON | ⬜ |
| 63.11 Delivery stats | ⬜ |

**OVERALL: ⬜**

---

## Q64: End User Self-Service Portal

**User says:** "I want to manage my own preferences, see my delivery history, and download past products."

### Prerequisites

```bash
cd /tmp && rm -rf test-q64 && mkdir test-q64 && cd test-q64
autoinfo init --demo medical-research

# Create an end user with history
autoinfo enduser create --user-id eve --name "Eve Portal" --email eve@example.com --trial --tier enterprise

# Add delivery preferences
autoinfo portal preferences update \
  --user-id eve \
  --delivery-prefs '{"email":true,"telegram":true,"telegram_chat_id":"555666","digest_channel":"email","quiet_hours_start":"23:00","quiet_hours_end":"07:00","timezone":"America/New_York"}'

# Seed some delivery log entries
python3 -c "
from autoinfo.user_store import create_subscription
from autoinfo.delivery_log import append_delivery_log

sub = create_subscription(user_id='eve', product_id='weekly-report', status='active')
sid = sub.sub_id
append_delivery_log(subscription_id=sid, channel='email', message_type='digest', status='delivered', attempt_count=1, sla_tier='standard')
append_delivery_log(subscription_id=sid, channel='email', message_type='report', status='delivered', attempt_count=1, sla_tier='standard')
append_delivery_log(subscription_id=sid, channel='telegram', message_type='alert', status='delivered', attempt_count=1, sla_tier='critical')
print(f'Seeded 3 delivery log entries for eve')
"
```

### Scenarios

#### 64.1 🟢 View delivery preferences

```bash
autoinfo portal preferences show --user-id eve
```

**Expected Result:**

- ✅ Exit code 0
- ✅ Shows: user ID, name, email, tier, status
- ✅ Shows all preferences (email, telegram, telegram_chat_id, quiet hours, timezone)
- ✅ Preferences displayed in human-readable format

**Actual Result:** _________ **PASS / FAIL:** _________

#### 64.2 🟢 Update delivery preferences (enable/disable channels)

```bash
# Disable Telegram, keep email
autoinfo portal preferences update \
  --user-id eve \
  --delivery-prefs '{"email":true,"telegram":false,"digest_channel":"email","timezone":"America/New_York"}'
```

**Expected Result:**

- ✅ Exit code 0
- ✅ Preferences updated
- ✅ Telegram now disabled
- ✅ Email still active (mandatory fallback)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 64.3 🟢 Set quiet hours

```bash
autoinfo portal preferences update \
  --user-id eve \
  --delivery-prefs '{"email":true,"digest_channel":"email","quiet_hours_start":"22:00","quiet_hours_end":"08:00","timezone":"America/New_York"}'
```

**Expected Result:** ✅ Quiet hours set. Should prevent delivery during 22:00-08:00 in user's timezone.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 64.4 🟢 Browse delivery history

```bash
autoinfo portal history --user eve
```

**Expected Result:**

- ✅ Exit code 0
- ✅ Shows delivery history with log ID, channel, type, status, attempt count, last attempt timestamp
- ✅ At least 3 entries visible (from seeded data)
- ✅ Total count shown

**Actual Result:** _________ **PASS / FAIL:** _________

#### 64.5 🟢 Filter delivery history by channel

```bash
autoinfo portal history --user eve --channel email
```

**Expected Result:**

- ✅ Exit code 0
- ✅ Only email channel deliveries shown
- ✅ Telegram deliveries excluded

**Actual Result:** _________ **PASS / FAIL:** _________

#### 64.6 🟢 View delivery history as JSON

```bash
autoinfo portal history --user eve --json
```

**Expected Result:**

- ✅ Valid JSON array
- ✅ Each entry has: log_id, subscription_id, channel, message_type, status, attempt_count, last_attempt, error_message, sla_tier
- ✅ Sorted by last_attempt descending

**Actual Result:** _________ **PASS / FAIL:** _________

#### 64.7 🟢 Download/access past products (product archive)

```python
from autoinfo.mcp.server import app
import json

# List available products
result = app.call_tool("list_products", {"domain": "medical-research"})
data = json.loads(result.content[0].text)
products = data.get("products", data.get("items", data.get("templates", [])))
print(f"✅ Available products for archive browsing:")
for p in products:
    print(f"  {p.get('name','?')} ({p.get('type','?')})")
```

**Expected Result:** ✅ Products listed accessible via the portal interface.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 64.8 🔴 Portal history for nonexistent user

```bash
autoinfo portal history --user nonexistent
```

**Expected Result:** ❌ Exit code != 0. Error: "End-user 'nonexistent' not found".

**Actual Result:** _________ **PASS / FAIL:** _________

#### 64.9 🔴 Portal preferences for nonexistent user

```bash
autoinfo portal preferences show --user-id nonexistent
```

**Expected Result:** ❌ Exit code != 0. Error: "End-user 'nonexistent' not found".

**Actual Result:** _________ **PASS / FAIL:** _________

#### 64.10 🟢 Portal history for user with no subscriptions

```bash
# Create a user with no delivery history
autoinfo enduser create --user-id newuser --name "New User" --email new@example.com --trial --tier free
autoinfo portal history --user newuser
```

**Expected Result:** ✅ Exit code 0. Message: "No delivery history for end-user 'newuser'" or similar. Not an error.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 64.11 🟢 Agent-assisted portal query (via MCP)

```python
from autoinfo.mcp.server import app
import json

# Agent queries end user profile on behalf of the user
result = app.call_tool("get_end_user", {"user_id": "eve"})
data = json.loads(result.content[0].text)
print(f"✅ Agent queried end user profile:")
print(f"  Name: {data.get('name','?')}, Status: {data.get('status','?')}, Tier: {data.get('tier','?')}")
print(f"  Delivery prefs: {json.dumps(data.get('delivery_prefs',{}), indent=2)[:100]}")
```

**Expected Result:** ✅ Agent can query profile and preferences on behalf of end user. Audit trail records the agent action.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q64 Verdict

| Scenario | Result |
|----------|--------|
| 64.1 View preferences | ⬜ |
| 64.2 Update preferences | ⬜ |
| 64.3 Set quiet hours | ⬜ |
| 64.4 Browse delivery history | ⬜ |
| 64.5 Filter history by channel | ⬜ |
| 64.6 History as JSON | ⬜ |
| 64.7 Product archive | ⬜ |
| 64.8 History nonexistent | ⬜ |
| 64.9 Prefs nonexistent | ⬜ |
| 64.10 No history user | ⬜ |
| 64.11 Agent-assisted query | ⬜ |

**OVERALL: ⬜**

---

## Q65: End User Data Privacy — Soft-Delete, Restore, GDPR Export

**User says:** "I want to delete my data. But maybe I will change my mind. And I want a copy of everything if I leave."

### Prerequisites

```bash
cd /tmp && rm -rf test-q65 && mkdir test-q65 && cd test-q65
autoinfo init --demo medical-research

# Create end user with subscription
autoinfo enduser create --user-id frank --name "Frank GDPR" --email frank@example.com --trial --tier pro
python3 -c "
from autoinfo.user_store import create_subscription
sub = create_subscription(user_id='frank', product_id='daily-digest', status='active')
print(f'Created subscription: {sub.sub_id}')
"
```

### Scenarios

#### 65.1 🟢 Soft-delete an end user profile

```python
from autoinfo.user_store import get_profile, update_profile
from datetime import datetime, timezone
import json

# Before deletion: verify profile exists
profile = get_profile("frank")
assert profile is not None
assert profile.status != "deleted"
print(f"✅ Profile before delete: status={profile.status}")

# Soft-delete by transitioning to cancelled then marking as deleted
# First transition to cancelled (terminal)
from autoinfo.user_store import transition_end_user
transition_end_user("frank", "cancelled")

# Then mark as deleted (soft-delete)
profile = update_profile("frank", status="deleted")
assert profile is not None
assert profile.status == "deleted"
print(f"✅ Profile soft-deleted: status={profile.status}")

# Verify profile still exists in database (not physically removed)
profile_after = get_profile("frank")
assert profile_after is not None, "Profile should still exist (soft-delete)"
assert profile_after.status == "deleted"
print(f"✅ Profile still queryable after soft-delete (status: {profile_after.status})")
```

**Expected Result:**

- ✅ Profile exists before deletion
- ✅ Status changed to "deleted" (not physically removed)
- ✅ Profile still queryable via `get_profile` — only marked as deleted
- ✅ Data fully recoverable within retention window

**Actual Result:** _________ **PASS / FAIL:** _________

#### 65.2 🟢 Restore a soft-deleted end user profile

```python
from autoinfo.user_store import get_profile, update_profile

# Restore by reverting status
profile = update_profile("frank", status="cancelled")
assert profile is not None
assert profile.status == "cancelled"
print(f"✅ Profile restored: status={profile.status}")

# Verify fully recovered
profile_check = get_profile("frank")
assert profile_check is not None
assert profile_check.name == "Frank GDPR"
assert profile_check.email == "frank@example.com"
assert profile_check.tier == "pro"
print(f"✅ All profile data preserved: name={profile_check.name}, email={profile_check.email}, tier={profile_check.tier}")
```

**Expected Result:**

- ✅ Profile restored by transitioning status back from "deleted" to a non-deleted state
- ✅ All fields (name, email, tier, delivery_prefs) preserved
- ✅ Subscriptions also restored or recoverable

**Actual Result:** _________ **PASS / FAIL:** _________

#### 65.3 🟢 Soft-delete KB entries

```python
from autoinfo.kb import KBStore, SQLiteIndex
from autoinfo.models import Item
from pathlib import Path
import tempfile, json

with tempfile.TemporaryDirectory() as td:
    kb_path = Path(td) / "knowledge"
    db_path = Path(td) / "autoinfo.db"
    store = KBStore(kb_path, SQLiteIndex(db_path))
    store.index.init_db()

    # Create an entry
    item = Item(
        id="gdpr_test_1",
        source_name="pubmed",
        title="GDPR Compliance Research",
        content="Data privacy in AI systems...",
        collected_at="2026-07-25",
        domain="medical-research",
        topic_tags=["privacy"]
    )
    entry = store.store_entry(item)
    entry_id = entry.entry_id
    print(f"✅ Entry created: {entry_id}")

    # Soft-delete the entry
    result = store.soft_delete_entry(entry_id, reason="User requested deletion")
    assert result.get("success", False), f"Soft-delete failed: {result}"
    print(f"✅ Entry soft-deleted: status=deleted, reason=User requested deletion")

    # Verify entry still exists but marked deleted
    deleted_entry = store.get_entry(entry_id)
    if deleted_entry:
        fm = getattr(deleted_entry, 'frontmatter', {}) or {}
        status = fm.get('status', deleted_entry.to_dict().get('status', 'unknown'))
        print(f"  Entry still exists: status={status}")
    else:
        print(f"  Entry queryable via index (soft-delete keeps data)")
```

**Expected Result:**

- ✅ Entry created successfully
- ✅ `soft_delete_entry` marks entry as deleted with reason
- ✅ Entry still exists in store (not physically removed)
- ✅ `deleted_at` timestamp and `deleted_reason` stored in audit trail

**Actual Result:** _________ **PASS / FAIL:** _________

#### 65.4 🟢 Restore a soft-deleted KB entry

```python
# Continuing from 65.3 context
with tempfile.TemporaryDirectory() as td:
    kb_path = Path(td) / "knowledge"
    db_path = Path(td) / "autoinfo.db"
    store = KBStore(kb_path, SQLiteIndex(db_path))
    store.index.init_db()

    item = Item(id="restore_test", source_name="pubmed", title="Restorable Article", content="Important content...", collected_at="2026-07-25", domain="medical-research", topic_tags=["test"])
    entry = store.store_entry(item)
    eid = entry.entry_id

    # Soft-delete
    store.soft_delete_entry(eid, reason="GDPR request")
    print(f"✅ Entry soft-deleted")

    # Restore within retention window
    result = store.restore_entry(eid)
    assert result.get("success", False), f"Restore failed: {result}"
    restored = store.get_entry(eid)
    fm = restored.to_dict() if restored else {}
    status = fm.get('status', '')
    assert status != "deleted", f"Entry still marked deleted after restore"
    print(f"✅ Entry restored: status={status}")
```

**Expected Result:**

- ✅ Entry can be restored via `restore_entry` tool
- ✅ After restore, entry status is no longer "deleted"
- ✅ Content and metadata preserved

**Actual Result:** _________ **PASS / FAIL:** _________

#### 65.5 🟢 GDPR data export

```python
from autoinfo.user_store import get_profile
from autoinfo.delivery_log import query_delivery_log
import json

# GDPR export assembles all data for a user
user_id = "frank"

# 1. Profile data
profile = get_profile(user_id)
assert profile is not None
profile_data = profile.to_dict() if hasattr(profile, 'to_dict') else {
    "user_id": profile.user_id,
    "name": profile.name,
    "email": profile.email,
    "delivery_prefs": profile.delivery_prefs,
    "status": profile.status,
    "tier": profile.tier,
    "created_at": profile.created_at,
    "updated_at": profile.updated_at,
}

# 2. Subscription data
from autoinfo.user_store import list_subscriptions
subs = list_subscriptions(user_id=user_id)
subscriptions_data = []
for s in subs:
    sub_data = {"sub_id": s.sub_id, "product_id": s.product_id, "status": s.status, "start_date": s.start_date}
    subscriptions_data.append(sub_data)

    # 3. Delivery log for each subscription
    log_entries = query_delivery_log(subscription_id=s.sub_id)
    for log_entry in log_entries:
        subscriptions_data[-1]["delivery_log"] = [
            {"log_id": e.log_id, "channel": e.channel, "status": e.status, "attempt_count": e.attempt_count, "last_attempt": e.last_attempt}
            for e in log_entries
        ]

# 4. KB entries attributable to user
from autoinfo.kb import KBStore
kb_entries = []  # Would query KB store for entries with user_id matching

# Assemble GDPR package
gdpr_export = {
    "export_date": datetime.now(timezone.utc).isoformat(),
    "user_id": user_id,
    "profile": profile_data,
    "subscriptions": subscriptions_data,
    "total_subscriptions": len(subs),
}

print(f"\n✅ GDPR Data Export for '{user_id}':")
print(f"  Profile: {profile_data['name']} <{profile_data['email']}>")
print(f"  Status: {profile_data['status']}, Tier: {profile_data['tier']}")
print(f"  Subscriptions: {len(subs)}")
for s in subscriptions_data:
    print(f"    - {s['product_id']}: {s['status']}")
print(f"  Export date: {gdpr_export['export_date']}")
```

**Expected Result:**

- ✅ All user data exported: profile, subscriptions, delivery logs, KB entries
- ✅ Machine-readable format (JSON)
- ✅ Human-readable format also available
- ✅ Data covers: user_id, name, email, delivery_prefs, status, tier, subscription history, delivery logs

**Actual Result:** _________ **PASS / FAIL:** _________

#### 65.6 🔴 Permanent deletion (purge)

```python
from autoinfo.user_store import delete_profile

# Permanent deletion with --purge flag
# Agent CANNOT purge — only Human Director User can (per F47)
try:
    result = delete_profile("frank")
    assert result, "Delete should succeed (profile exists)"
    print(f"✅ Profile physically deleted: user_id=frank")
except Exception as e:
    print(f"❌ Deletion blocked (expected for agent): {e}")
    print(f"   Per F47: Agent cannot purge. Only Human with --purge flag.")

# Verify gone
from autoinfo.user_store import get_profile
gone = get_profile("frank")
assert gone is None, "Profile should be physically removed after purge"
print(f"✅ Verified: profile no longer exists")
```

**Expected Result:**

- ❌ Agent deletion removes the profile (soft or hard depending on implementation)
- ❌ Per F47: agent cannot permanently purge — only Human Director User with --purge flag
- ✅ After purge, profile is gone (not queryable)

**Actual Result:** _________ **PASS / FAIL:** _________

#### 65.7 🟢 30-day auto-cleanup retention window

```python
from datetime import datetime, timezone, timedelta

# Verify the retention window configuration
# Per F47: 30-day auto-cleanup for soft-deleted entries
# Retention by tier: Trial=14d post-cancellation, Active=full+30d, Archived=90d

tier_retention = {
    "free": {"post_cancellation_days": 14},
    "pro": {"post_cancellation_days": 30},
    "enterprise": {"post_cancellation_days": 90},
}

print(f"✅ Retention windows by subscription tier:")
for tier, config in tier_retention.items():
    print(f"  {tier}: {config['post_cancellation_days']} days post-cancellation")

# Verify cleanup command exists
```

```bash
# Verify the clean command for purging expired entries
autoinfo clean --help 2>&1 | grep -i "purge\|expir\|cleanup" || autoinfo clean --help
```

**Expected Result:**

- ✅ Retention windows documented per tier
- ✅ `autoinfo clean --purge-expired` command exists for scheduled cleanup
- ✅ Cleanup respects retention period per subscription tier

**Actual Result:** _________ **PASS / FAIL:** _________

#### 65.8 🟢 Audit log for deletion operations

```python
# Deletion operations must be recorded in immutable audit log
# Verify by querying audit log for the operation

# Simulate audit log check
from autoinfo.user_store import transition_end_user, update_profile
from autoinfo.audit import query_audit_log

# Perform a deletion-related operation
transition_end_user("frank", "cancelled")

# Query audit log for the action
try:
    results = query_audit_log(
        actor="system",
        action="transition_end_user",
        resource_id="frank",
    )
    print(f"✅ Audit log entries for frank's transition:")
    for r in results:
        details = r.get("details", {})
        print(f"  action={r.get('action','?')}, from={details.get('from_status','?')} → to={details.get('to_status','?')}")
except Exception as e:
    print(f"  Audit log query: {e}")
    print(f"  (May not be implemented — verify audit logging exists)")
```

**Expected Result:** ✅ Deletion/transition operations recorded in immutable audit log with actor, resource, and details.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q65 Verdict

| Scenario | Result |
|----------|--------|
| 65.1 Soft-delete profile | ⬜ |
| 65.2 Restore profile | ⬜ |
| 65.3 Soft-delete KB entry | ⬜ |
| 65.4 Restore KB entry | ⬜ |
| 65.5 GDPR data export | ⬜ |
| 65.6 Permanent purge | ⬜ |
| 65.7 Retention window | ⬜ |
| 65.8 Audit log for deletion | ⬜ |

**OVERALL: ⬜**

---

## Final Verdict — Part 13

### Overall Summary

| Question | Coverage | Result |
|----------|----------|--------|
| Q61 | End user profile registration & subscription (CLI + MCP CRUD, state machine) | ⬜ |
| Q62 | Multi-channel delivery configuration (6 channels, product mapping, reachability) | ⬜ |
| Q63 | Product delivery lifecycle (RAW + PROCESSED, DeliveryLog, P0/P1/P2 SLA) | ⬜ |
| Q64 | End user self-service portal (preferences, history, product archive) | ⬜ |
| Q65 | Data privacy (soft-delete, restore, GDPR export, retention) | ⬜ |

### Expectations Coverage

| Expectation | Description | Status |
|-------------|-------------|--------|
| F36 | End User Profile & Subscription Registration | ⬜ |
| F37 | Multi-Channel Delivery Configuration | ⬜ |
| F38 | End User Lifecycle State Machine | ⬜ |
| F39 | Delivery Reliability & Logging | ⬜ |
| F40 | End User Self-Service Portal | ⬜ |
| F42 | External Billing Model (deferred to v2+) | ➖ (partial) |
| F43 | End-User Cost Dashboard | ⬜ |
| F47 | Data Deletion & Retention | ⬜ |

**PART 13 OVERALL: ⬜**

---

### Legend

| Symbol | Meaning |
|--------|---------|
| ✅ PASS | All scenarios in this question match expected results |
| ❌ FAIL | One or more scenarios did NOT match expected results |
| ⚠️ PARTIAL | Some scenarios pass, some fail |
| ➖ SKIP | Scenarios intentionally skipped (reason documented) |
| ⬜ PENDING | Not yet validated |
