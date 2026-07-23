# Part 7: REST API & Web UI (Q47-Q48)

**Coverage:** FastAPI REST endpoints (port 8741), Web UI dashboard, health, search, CRUD

---

## Q47: REST API Endpoints

**User says:** "I want to access my knowledge base over HTTP."

### Prerequisites
```bash
cd /tmp && rm -rf test-q47 && mkdir test-q47 && cd test-q47
autoinfo init --demo medical-research
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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 47.2 🟢 List entries (with pagination)
```bash
curl -s "http://127.0.0.1:8741/api/v1/entries?domain=medical-research&limit=5&offset=0"
```
**Expected Result:** ✅ Returns JSON with entries array, total_count, pagination info.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 47.3 🟢 Get single entry by ID
```bash
# First get an entry ID
ENTRY_ID=$(curl -s "http://127.0.0.1:8741/api/v1/entries?domain=medical-research&limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); entries=d.get('entries',[]); print(entries[0]['entry_id'] if entries else '')")
if [ -n "$ENTRY_ID" ]; then
    curl -s "http://127.0.0.1:8741/api/v1/entries/$ENTRY_ID"
fi
```
**Expected Result:** ✅ Returns full entry with metadata and content.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 47.4 🟢 Search entries (FTS5)
```bash
curl -s -X POST "http://127.0.0.1:8741/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "IVF", "domain": "medical-research", "mode": "hybrid", "limit": 5}'
```
**Expected Result:** ✅ Returns matching entries with relevance scores.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 47.5 🟢 Vector search
```bash
curl -s -X POST "http://127.0.0.1:8741/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "embryo development", "domain": "medical-research", "mode": "vector", "limit": 5}'
```
**Expected Result:** ✅ Returns entries using semantic vector search.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 47.6 🟢 Faceted search with filters
```bash
curl -s -X POST "http://127.0.0.1:8741/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"domain": "medical-research", "filters": {"source_type": "pubmed", "relevance_min": 50}}'
```
**Expected Result:** ✅ Returns filtered entries matching all criteria.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 47.7 🟢 Dashboard stats
```bash
curl -s http://127.0.0.1:8741/dashboard
```
**Expected Result:** ✅ Returns HTML dashboard or JSON stats with collection counts, source health.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 47.8 🟢 API returns proper CORS headers
```bash
curl -s -I -X OPTIONS http://127.0.0.1:8741/health 2>&1 | grep -i "access-control-allow-origin"
```
**Expected Result:** ✅ CORS headers present: `Access-Control-Allow-Origin: *`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 47.9 🔴 404 for nonexistent endpoint
```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8741/api/v1/nonexistent
```
**Expected Result:** ❌ HTTP 404. Returns JSON error, not HTML.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 47.10 🔴 422 for invalid parameters
```bash
curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8741/api/v1/entries?limit=-1"
```
**Expected Result:** ❌ HTTP 422. Validation error with details.

**Actual Result:** _________ **PASS / FAIL:** _________

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
| 47.9 404 handling | ⬜ |
| 47.10 422 validation | ⬜ |

**OVERALL: ⬜**

---

## Q48: Web UI Dashboard

**User says:** "I want a browser-based dashboard to see my collection status."

### Prerequisites
```bash
cd /tmp && rm -rf test-q48 && mkdir test-q48 && cd test-q48
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

**Actual Result:** _________ **PASS / FAIL:** _________

#### 48.2 🟢 Dashboard contains collection stats section
```bash
curl -s http://127.0.0.1:8742/dashboard | grep -i "collect\|stat\|entry\|source" | head -5
```
**Expected Result:** ✅ Dashboard shows collection statistics, KB entry counts, source health.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 48.3 🟢 Dashboard is responsive
```bash
curl -s http://127.0.0.1:8742/dashboard | grep -i "bootstrap\|container\|meta.*viewport"
```
**Expected Result:** ✅ Bootstrap container/viewport meta tag present for responsive design.

**Actual Result:** _________ **PASS / FAIL:** _________

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
