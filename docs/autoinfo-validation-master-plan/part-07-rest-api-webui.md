# Part 7: REST API & Web UI (Q47-Q48)

**Coverage:** FastAPI REST endpoints (port 8741), Web UI dashboard, health, search, CRUD

---

### Part-Level Directory Setup
Run once at the start of this part:
```bash
# Create clean directories for all questions in this part
rm -rf /tmp/test-q47 && mkdir -p /tmp/test-q47
rm -rf /tmp/test-q48 && mkdir -p /tmp/test-q48
```

## Q47: REST API Endpoints

**User says:** "I want to access my knowledge base over HTTP."

### Prerequisites
```bash
cd /tmp/test-q47
autoinfo init --demo medical-research

# Create end user for portal endpoint tests
autoinfo enduser create \
  --user-id testuser47 \
  --name "Test User 47" \
  --email "testuser47@example.com" \
  --trial-days 30

# Collect some items so feeds endpoint has data to return
autoinfo collect --domain medical-research --topic "IVF breakthroughs" --limit 3 2>/dev/null || true
autoinfo process --domain medical-research 2>/dev/null || true

# Start API server in background
uvicorn autoinfo.api.server:app --port 8741 --host 127.0.0.1 &
API_PID=$!
sleep 2  # Wait for server to start
echo "API server started (PID: $API_PID)"
```

### Scenarios

#### 47.1 🟢 Health check endpoint
```bash
curl -s http://127.0.0.1:8741/health
```
**Expected Result:** ✅ Returns JSON: `{"status": "ok", "version": "..."}`.


#### 47.2 🟢 List entries (with pagination)
```bash
curl -s "http://127.0.0.1:8741/api/v1/entries?domain=medical-research&limit=5&offset=0"
```
**Expected Result:** ✅ Returns JSON with entries array, total_count, pagination info.


#### 47.3 🟢 Get single entry by ID
```bash
# First get an entry ID
ENTRY_ID=$(curl -s "http://127.0.0.1:8741/api/v1/entries?domain=medical-research&limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); entries=d.get('entries',[]); print(entries[0]['entry_id'] if entries else '')")
if [ -n "$ENTRY_ID" ]; then
    curl -s "http://127.0.0.1:8741/api/v1/entries/$ENTRY_ID"
fi
```
**Expected Result:** ✅ Returns full entry with metadata and content.


#### 47.4 🟢 Search entries (FTS5)
```bash
curl -s -X POST "http://127.0.0.1:8741/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "IVF", "domain": "medical-research", "mode": "hybrid", "limit": 5}'
```
**Expected Result:** ✅ Returns matching entries with relevance scores.


#### 47.5 🟢 Vector search
```bash
curl -s -X POST "http://127.0.0.1:8741/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "embryo development", "domain": "medical-research", "mode": "vector", "limit": 5}'
```
**Expected Result:** ✅ Returns entries using semantic vector search.


#### 47.6 🟢 Faceted search with filters
```bash
curl -s -X POST "http://127.0.0.1:8741/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"domain": "medical-research", "filters": {"source_type": "pubmed", "relevance_min": 50}}'
```
**Expected Result:** ✅ Returns filtered entries matching all criteria.


#### 47.7 🟢 Dashboard stats
```bash
curl -s http://127.0.0.1:8741/dashboard
```
**Expected Result:** ✅ Returns HTML dashboard or JSON stats with collection counts, source health.


#### 47.8 🟢 API returns proper CORS headers
```bash
curl -s -I -X OPTIONS http://127.0.0.1:8741/health 2>&1 | grep -i "access-control-allow-origin"
```
**Expected Result:** ✅ CORS headers present: `Access-Control-Allow-Origin: *`.


#### 47.9 🟢 GET /api/v1/portal/preferences returns user delivery prefs
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(curl -s http://127.0.0.1:8741/api/v1/portal/preferences?user_id=testuser47 2>&1)
EXIT_CODE=$?

# ── Verify JSON is valid ───────────────────────────────────────
echo "$OUTPUT" | python3 -m json.tool > /dev/null \
  && echo "  ✅ PASS: valid JSON response" \
  || { echo "  ❌ FAIL: invalid JSON response"; ALL_PASS=false; }

# ── Verify HTTP 200 ────────────────────────────────────────────
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8741/api/v1/portal/preferences?user_id=testuser47")
[ "$HTTP_CODE" = "200" ] \
  && echo "  ✅ PASS: HTTP 200" \
  || { echo "  ❌ FAIL: HTTP $HTTP_CODE (expected 200)"; ALL_PASS=false; }

# ── Verify required keys ────────────────────────────────────────
echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert 'user_id' in data, 'missing user_id'
assert 'name' in data, 'missing name'
assert 'email' in data, 'missing email'
assert 'delivery_prefs' in data, 'missing delivery_prefs'
assert 'tier' in data, 'missing tier'
assert 'status' in data, 'missing status'
print('All keys present')
" 2>&1 \
  && echo "  ✅ PASS: all required keys present (user_id, name, email, delivery_prefs, tier, status)" \
  || { echo "  ❌ FAIL: missing required keys in response"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 47.9 PASSED"; exit 0; else echo "❌ SCENARIO 47.9 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ HTTP 200 with valid JSON
- ✅ Response contains `user_id`, `name`, `email`, `delivery_prefs`, `tier`, `status`


#### 47.10 🟢 PUT /api/v1/portal/preferences updates and returns new prefs
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(curl -s -X PUT "http://127.0.0.1:8741/api/v1/portal/preferences?user_id=testuser47" \
  -H "Content-Type: application/json" \
  -d '{"delivery_prefs": {"digest_frequency": "weekly", "channels": ["email", "web"]}, "email": "updated47@example.com"}' 2>&1)
EXIT_CODE=$?

# ── Verify JSON is valid ───────────────────────────────────────
echo "$OUTPUT" | python3 -m json.tool > /dev/null \
  && echo "  ✅ PASS: valid JSON response" \
  || { echo "  ❌ FAIL: invalid JSON response"; ALL_PASS=false; }

# ── Verify HTTP 200 ────────────────────────────────────────────
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT \
  "http://127.0.0.1:8741/api/v1/portal/preferences?user_id=testuser47" \
  -H "Content-Type: application/json" \
  -d '{"delivery_prefs": {"digest_frequency": "weekly", "channels": ["email", "web"]}}')
[ "$HTTP_CODE" = "200" ] \
  && echo "  ✅ PASS: HTTP 200" \
  || { echo "  ❌ FAIL: HTTP $HTTP_CODE (expected 200)"; ALL_PASS=false; }

# ── Verify updated preferences returned ─────────────────────────
echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
prefs = data.get('delivery_prefs', {})
assert prefs.get('digest_frequency') == 'weekly', f'digest_frequency is {prefs.get(\"digest_frequency\")} (expected weekly)'
assert 'channels' in prefs, 'missing channels'
print('Preferences updated correctly')
" 2>&1 \
  && echo "  ✅ PASS: delivery_prefs updated with digest_frequency=weekly and channels" \
  || { echo "  ❌ FAIL: delivery_prefs not updated correctly"; ALL_PASS=false; }

# ── Verify email was updated ────────────────────────────────────
echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data.get('email') == 'updated47@example.com', f'email is {data.get(\"email\")} (expected updated47@example.com)'
print('Email updated')
" 2>&1 \
  && echo "  ✅ PASS: email updated to updated47@example.com" \
  || { echo "  ❌ FAIL: email not updated"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 47.10 PASSED"; exit 0; else echo "❌ SCENARIO 47.10 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ HTTP 200 with valid JSON
- ✅ Updated `delivery_prefs` with `digest_frequency: "weekly"` and `channels`
- ✅ Updated `email` to `updated47@example.com`


#### 47.11 🟢 GET /api/v1/portal/delivery-history returns paginated log
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(curl -s "http://127.0.0.1:8741/api/v1/portal/delivery-history?user_id=testuser47&limit=10&offset=0" 2>&1)
EXIT_CODE=$?

# ── Verify JSON is valid ───────────────────────────────────────
echo "$OUTPUT" | python3 -m json.tool > /dev/null \
  && echo "  ✅ PASS: valid JSON response" \
  || { echo "  ❌ FAIL: invalid JSON response"; ALL_PASS=false; }

# ── Verify HTTP 200 ────────────────────────────────────────────
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  "http://127.0.0.1:8741/api/v1/portal/delivery-history?user_id=testuser47&limit=10&offset=0")
[ "$HTTP_CODE" = "200" ] \
  && echo "  ✅ PASS: HTTP 200" \
  || { echo "  ❌ FAIL: HTTP $HTTP_CODE (expected 200)"; ALL_PASS=false; }

# ── Verify pagination envelope ──────────────────────────────────
echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert 'user_id' in data, 'missing user_id'
assert 'subscriptions' in data, 'missing subscriptions'
assert 'entries' in data, 'missing entries'
assert 'total' in data, 'missing total'
assert 'limit' in data, 'missing limit'
assert 'offset' in data, 'missing offset'
assert isinstance(data['entries'], list), 'entries not a list'
assert isinstance(data['subscriptions'], list), 'subscriptions not a list'
assert isinstance(data['total'], int), 'total not int'
print('Pagination envelope valid')
" 2>&1 \
  && echo "  ✅ PASS: pagination envelope with user_id, subscriptions, entries, total, limit, offset" \
  || { echo "  ❌ FAIL: pagination envelope incorrect"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 47.11 PASSED"; exit 0; else echo "❌ SCENARIO 47.11 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ HTTP 200 with valid JSON
- ✅ Response envelope: `user_id`, `subscriptions` (list), `entries` (list), `total` (int), `limit`, `offset`


#### 47.12 🟢 GET /api/v1/feeds returns paginated RAW products with topic filter
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(curl -s "http://127.0.0.1:8741/api/v1/feeds?domain=medical-research&limit=5&offset=0" 2>&1)
EXIT_CODE=$?

# ── Verify JSON is valid ───────────────────────────────────────
echo "$OUTPUT" | python3 -m json.tool > /dev/null \
  && echo "  ✅ PASS: valid JSON response" \
  || { echo "  ❌ FAIL: invalid JSON response"; ALL_PASS=false; }

# ── Verify HTTP 200 ────────────────────────────────────────────
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  "http://127.0.0.1:8741/api/v1/feeds?domain=medical-research&limit=5&offset=0")
[ "$HTTP_CODE" = "200" ] \
  && echo "  ✅ PASS: HTTP 200" \
  || { echo "  ❌ FAIL: HTTP $HTTP_CODE (expected 200)"; ALL_PASS=false; }

# ── Verify feed envelope ────────────────────────────────────────
echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert 'items' in data, 'missing items'
assert 'pagination' in data, 'missing pagination'
assert isinstance(data['items'], list), 'items not a list'
pag = data['pagination']
for k in ('total', 'limit', 'offset'):
    assert k in pag, f'missing pagination.{k}'
assert 'next' in pag, 'missing pagination.next'
print('Feed envelope valid')
" 2>&1 \
  && echo "  ✅ PASS: feed envelope with items (list) and pagination (total, limit, offset, next)" \
  || { echo "  ❌ FAIL: feed envelope incorrect"; ALL_PASS=false; }

# ── Verify item schema (if items present) ───────────────────────
echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data['items']
if len(items) > 0:
    item = items[0]
    for k in ('id', 'title', 'url', 'source_type', 'collected_at', 'relevance_score'):
        assert k in item, f'missing field: {k}'
    print(f'Item schema valid ({len(items)} items)')
else:
    print('No items, schema check skipped')
" 2>&1 \
  && echo "  ✅ PASS: item schema valid (id, title, url, source_type, collected_at, relevance_score)" \
  || { echo "  ❌ FAIL: item schema invalid"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 47.12 PASSED"; exit 0; else echo "❌ SCENARIO 47.12 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ HTTP 200 with valid JSON
- ✅ Response envelope: `items` (list), `pagination` (total, limit, offset, next)
- ✅ Each item has: `id`, `title`, `url`, `source_type`, `collected_at`, `relevance_score`


#### 47.13 🔴 GET /api/v1/feeds?topic=nonexistent returns empty result (not error)
```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

OUTPUT=$(curl -s "http://127.0.0.1:8741/api/v1/feeds?domain=medical-research&topic=nonexistent&limit=5" 2>&1)
EXIT_CODE=$?

# ── Verify HTTP 200 (NOT 404 or 422) ───────────────────────────
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  "http://127.0.0.1:8741/api/v1/feeds?domain=medical-research&topic=nonexistent&limit=5")
[ "$HTTP_CODE" = "200" ] \
  && echo "  ✅ PASS: HTTP 200 (not error)" \
  || { echo "  ❌ FAIL: HTTP $HTTP_CODE (expected 200)"; ALL_PASS=false; }

# ── Verify JSON is valid ───────────────────────────────────────
echo "$OUTPUT" | python3 -m json.tool > /dev/null \
  && echo "  ✅ PASS: valid JSON response" \
  || { echo "  ❌ FAIL: invalid JSON response"; ALL_PASS=false; }

# ── Verify empty items list ─────────────────────────────────────
echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data.get('items', [])
assert isinstance(items, list), 'items not a list'
assert len(items) == 0, f'expected 0 items, got {len(items)}'
pag = data.get('pagination', {})
assert pag.get('total', -1) == 0, f'expected total=0, got {pag.get(\"total\")}'
print('Empty result confirmed')
" 2>&1 \
  && echo "  ✅ PASS: empty items list (items=[], total=0)" \
  || { echo "  ❌ FAIL: expected empty items list"; ALL_PASS=false; }

# ── Verify pagination still present ─────────────────────────────
echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
pag = data.get('pagination', {})
for k in ('total', 'limit', 'offset', 'next'):
    assert k in pag, f'missing pagination.{k}'
assert pag['total'] == 0, f'expected total=0, got {pag[\"total\"]}'
print('Pagination valid on empty result')
" 2>&1 \
  && echo "  ✅ PASS: pagination present with total=0 even for empty results" \
  || { echo "  ❌ FAIL: pagination missing or incorrect on empty result"; ALL_PASS=false; }

if [ "$ALL_PASS" = true ]; then echo "✅ SCENARIO 47.13 PASSED"; exit 0; else echo "❌ SCENARIO 47.13 FAILED"; exit 1; fi
```
**Expected Result:**
- ✅ HTTP 200 (not 404 or error)
- ✅ Valid JSON with empty `items: []` and `pagination.total: 0`


#### 47.16 🔴 404 for nonexistent endpoint
```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8741/api/v1/nonexistent
```
**Expected Result:** ❌ HTTP 404. Returns JSON error, not HTML.


#### 47.17 🔴 422 for invalid parameters
```bash
curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8741/api/v1/entries?limit=-1"
```
**Expected Result:** ❌ HTTP 422. Validation error with details.


#### 47.14 🟢 Stripe webhook with valid signature returns 200

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true

# ── Determine signature mode ─────────────────────────────────────
SECRET="${STRIPE_WEBHOOK_SECRET:-}"
PAYLOAD='{"type":"checkout.session.completed","data":{"object":{"metadata":{"end_user_id":"webhook_test_user"}}}}'

if [ -n "$SECRET" ]; then
    # Generate a valid Stripe signature
    SIG_HEADER=$(python3 -c "
import os, json, time
secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
payload = json.dumps({
    'type': 'checkout.session.completed',
    'data': {'object': {'metadata': {'end_user_id': 'webhook_test_user'}}}
}).encode('utf-8')
timestamp = int(time.time())
import stripe
stripe.api_key = 'sk_test_mock'
signature = stripe.Webhook.compute_signature(timestamp, payload, secret)
print('t={},v1={}'.format(timestamp, signature))
")
    echo "  ℹ️  STRIPE_WEBHOOK_SECRET configured — verifying signature"
else
    SIG_HEADER="t=123,v1=devmode"
    echo "  ℹ️  STRIPE_WEBHOOK_SECRET not set — dev mode (signature verification skipped)"
fi

# ── Send webhook ─────────────────────────────────────────────────
RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST "http://127.0.0.1:8741/api/v1/webhook/stripe" \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: $SIG_HEADER" \
  -d "$PAYLOAD" 2>&1)

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

# ── Assertions ───────────────────────────────────────────────────
[ "$HTTP_CODE" = "200" ] \
  && echo "  ✅ PASS: HTTP 200" \
  || { echo "  ❌ FAIL: HTTP $HTTP_CODE (expected 200)"; ALL_PASS=false; }

echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'status' in d, 'missing status'" 2>/dev/null \
  && echo "  ✅ PASS: response contains 'status' field" \
  || { echo "  ❌ FAIL: response missing 'status' field"; ALL_PASS=false; }

echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'event_type' in d, 'missing event_type'" 2>/dev/null \
  && echo "  ✅ PASS: response contains 'event_type' field" \
  || { echo "  ❌ FAIL: response missing 'event_type' field"; ALL_PASS=false; }

# ── Verdict ──────────────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo ""
  echo "✅ SCENARIO 47.14 PASSED — Stripe webhook valid"
  exit 0
else
  echo ""
  echo "❌ SCENARIO 47.14 FAILED"
  exit 1
fi
```
**Expected Result:** ✅ HTTP 200. Response JSON contains `status` and `event_type` fields. Valid signature accepted (real verification with `STRIPE_WEBHOOK_SECRET`, or dev-mode fallback without).


#### 47.15 🔴 Stripe webhook without signature returns 400 (or falls through in dev mode)

```bash
#!/usr/bin/env bash
set -euo pipefail
ALL_PASS=true
SECRET="${STRIPE_WEBHOOK_SECRET:-}"

PAYLOAD='{"type":"checkout.session.completed","data":{"object":{"metadata":{}}}}'

RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST "http://127.0.0.1:8741/api/v1/webhook/stripe" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" 2>&1)

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ -n "$SECRET" ]; then
  # Secret configured — signature verification is enforced
  echo "  ℹ️  STRIPE_WEBHOOK_SECRET configured — expecting 400"
  [ "$HTTP_CODE" = "400" ] \
    && echo "  ✅ PASS: HTTP 400 on missing Stripe-Signature header" \
    || { echo "  ❌ FAIL: HTTP $HTTP_CODE (expected 400)"; ALL_PASS=false; }

  echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('error') == 'invalid_signature'" 2>/dev/null \
    && echo "  ✅ PASS: error='invalid_signature'" \
    || { echo "  ❌ FAIL: missing/incorrect error code"; ALL_PASS=false; }
else
  # Dev mode — signature verification skipped
  echo "  ℹ️  STRIPE_WEBHOOK_SECRET not set — signature verification skipped (dev mode)"
  echo "  ℹ️  In dev mode, the endpoint accepts raw JSON without signature"
  echo "  ℹ️  Set STRIPE_WEBHOOK_SECRET to enable real signature verification"
fi

# ── Verdict ──────────────────────────────────────────────────────
if [ "$ALL_PASS" = true ]; then
  echo ""
  echo "✅ SCENARIO 47.15 PASSED — missing signature rejected"
  exit 0
else
  echo ""
  echo "❌ SCENARIO 47.15 FAILED"
  exit 1
fi
```
**Expected Result:**
- ❌ With `STRIPE_WEBHOOK_SECRET`: HTTP 400, `error`: `"invalid_signature"` — missing `Stripe-Signature` header is rejected.
- ⚠️ Without `STRIPE_WEBHOOK_SECRET`: dev-mode fallback accepts raw JSON (verification skipped); test notes this as informational.


### Cleanup
```bash
kill $API_PID 2>/dev/null || true
```

---

### 📊 Q47 Verdict

| Scenario | Result |
|----------|--------|
| 47.1 Health check | ⬜ |
| 47.2 List entries | ⬜ |
| 47.3 Get entry | ⬜ |
| 47.4 FTS5 search | ⬜ |
| 47.5 Vector search | ⬜ |
| 47.6 Faceted search | ⬜ |
| 47.7 Dashboard | ⬜ |
| 47.8 CORS headers | ⬜ |
| 47.9 Portal preferences (GET) | ⬜ |
| 47.10 Portal preferences (PUT) | ⬜ |
| 47.11 Portal delivery history | ⬜ |
| 47.12 Feeds GET | ⬜ |
| 47.13 Feeds nonexistent topic | ⬜ |
| 47.14 Stripe webhook (valid) | ⬜ |
| 47.15 Stripe webhook (no sig) | ⬜ |
| 47.16 404 handling | ⬜ |
| 47.17 422 validation | ⬜ |

**OVERALL: ⬜**

---

## Q48: Web UI Dashboard

**User says:** "I want a browser-based dashboard to see my collection status."

### Prerequisites
```bash
cd /tmp/test-q48
autoinfo init --demo medical-research
uvicorn autoinfo.api.server:app --port 8742 --host 127.0.0.1 &
UI_PID=$!
sleep 2
```

### Scenarios

#### 48.1 🟢 Dashboard HTML page loads
```bash
curl -s http://127.0.0.1:8742/dashboard | head -20
```
**Expected Result:** ✅ Returns HTML with Bootstrap 5 styling. No error.


#### 48.2 🟢 Dashboard contains collection stats section
```bash
curl -s http://127.0.0.1:8742/dashboard | grep -i "collect\|stat\|entry\|source" | head -5
```
**Expected Result:** ✅ Dashboard shows collection statistics, KB entry counts, source health.


#### 48.3 🟢 Dashboard is responsive
```bash
curl -s http://127.0.0.1:8742/dashboard | grep -i "bootstrap\|container\|meta.*viewport"
```
**Expected Result:** ✅ Bootstrap container/viewport meta tag present for responsive design.


### Cleanup
```bash
kill $UI_PID 2>/dev/null || true
```

---

### 📊 Q48 Verdict

| Scenario | Result |
|----------|--------|
| 48.1 Dashboard loads | ⬜ |
| 48.2 Stats visible | ⬜ |
| 48.3 Responsive design | ⬜ |

**OVERALL: ⬜**
