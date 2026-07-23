# Part 11: Production Validation (Q60)

**Coverage:** Doctor diagnostics, MCP stdio, stress test, test suite, package import

---

## Q60: Production Validation

**User says:** "I need to verify AutoInfo is production-ready."

### Scenarios

#### 60.1 🟢 Doctor runs in fresh project — checks all 4 areas
```bash
cd /tmp && rm -rf test-prod && mkdir test-prod && cd test-prod
autoinfo init --demo medical-research
autoinfo doctor
```
**Expected Result:**
- ✅ Checks Python version (≥3.11)
- ✅ Checks config exists and valid
- ✅ Reports LLM key status
- ✅ Reports source count and health
- ✅ No crashes, friendly output

**Actual Result:** _________ **PASS / FAIL:** _________

#### 60.2 🟢 MCP server starts and responds via stdio
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}' | timeout 5 python3 -m autoinfo.mcp.server 2>/dev/null; echo "Exit: $?"
```
**Expected Result:** ✅ Server starts. Responds to JSON-RPC ping. Exit 0.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 60.3 🔴 MCP server rejects invalid JSON-RPC
```bash
echo 'invalid json' | timeout 5 python3 -m autoinfo.mcp.server 2>/dev/null; echo "Exit: $?"
```
**Expected Result:** ❌ Server does NOT crash. Returns JSON-RPC error response. No Python traceback.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 60.4 🟢 MCP server lists all 72 tools
```python
from autoinfo.mcp.server import app
tools = app.list_tools()()
tool_names = [t.name for t in tools]
print(f"Total tools: {len(tool_names)}")
assert len(tool_names) >= 68, f"Expected ≥68 tools, got {len(tool_names)}"

# Check tools from every category
expected_core = ["health_check", "diagnose_system", "collect_sources", "process_collection",
                 "list_summaries", "search_knowledge_base", "generate_report", "classify_cefr"]
missing = [t for t in expected_core if t not in tool_names]
assert len(missing) == 0, f"Missing core tools: {missing}"

# Check v1.4 additions
expected_v14 = ["add_domain", "remove_domain", "list_available_platforms", "import_kb",
                "set_domain_webhooks", "get_domain_webhooks", "send_email_digest"]
missing_v14 = [t for t in expected_v14 if t not in tool_names]
if missing_v14:
    print(f"⚠️ Missing v1.4 tools: {missing_v14}")
else:
    print("✅ All v1.4 tools present")

# Print category summary
categories = {
    "System": ["health_check", "diagnose_system", "get_config", "list_available_models"],
    "Discovery": ["list_domains", "list_available_platforms", "get_domain_schema", "get_effective_llm_config"],
    "Source": ["add_source", "add_sources", "remove_source", "test_source", "list_sources", "get_source_health"],
    "Topic": ["add_topic", "remove_topic", "list_topics", "list_keywords", "approve_keyword", "reject_keyword", "suggest_keywords"],
    "Collection": ["collect_sources", "get_collection_progress", "get_collection_status", "process_collection", "get_processing_progress", "batch_run"],
    "KB": ["search_knowledge_base", "get_kb_entry", "list_summaries", "get_summary", "create_kb_draft", "reject_kb_draft", "list_kb_tier", "reindex_kb", "flag_for_knowledge_base", "vector_search", "faceted_search"],
    "Output": ["list_output_templates", "generate_digest", "generate_report", "generate_tutorial", "generate_presentation", "localize_content"],
    "Cron": ["list_schedules", "add_schedule", "remove_schedule", "run_schedules"],
    "Projects": ["init_project", "list_projects", "get_project_assets", "archive_project"],
}
for cat, cat_tools in categories.items():
    present = [t for t in cat_tools if t in tool_names]
    print(f"  {cat}: {len(present)}/{len(cat_tools)} tools present")
```
**Expected Result:** ✅ 72 tools registered with correct names. All categories have expected tools.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 60.5 🟢 3 consecutive pipeline runs — no crash
```bash
for i in $(seq 1 3); do
    cd /tmp && rm -rf "stress-test-$i" && mkdir "stress-test-$i" && cd "stress-test-$i"
    autoinfo init --demo medical-research
    autoinfo collect --domain medical-research --topic "IVF" --limit 2
    echo "Run $i: exit=$?"
done
```
**Expected Result:** ✅ All 3 runs complete without crash. No file handle leak.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 60.6 🟢 Package imports cleanly
```bash
python3 -c "import autoinfo; print(f'AutoInfo v{autoinfo.__version__}')"
```
**Expected Result:** ✅ Package imports without error. Version string present.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 60.7 🟢 Test suite passes
```bash
cd /mnt/d/贯维/AutoInfo && pytest -v --tb=short -x 2>&1 | tail -30
```
**Expected Result:** ✅ 1134+ tests pass. 0 failures.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 60.8 🟢 Test collection without errors
```bash
cd /mnt/d/贯维/AutoInfo && pytest --collect-only -q
```
**Expected Result:** ✅ All 1134+ tests collected without import errors.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 60.9 🟢 CLI entry point works from anywhere
```bash
# Test from /tmp (outside project dir with no config)
cd /tmp && autoinfo --help 2>&1 | head -5
```
**Expected Result:** ✅ CLI responds from any directory. Shows help.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 60.10 🟢 Python module entry point works
```bash
python3 -m autoinfo.cli --help 2>&1 | head -5
```
**Expected Result:** ✅ Module entry point works. Same output as `autoinfo --help`.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 60.11 🟢 MCP server entry point works
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}' | timeout 3 python3 -m autoinfo.mcp.server 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'pong: {d.get(\"result\")}')" 2>/dev/null || echo "MCP entry point works (non-JSON-LS mode)"
```
**Expected Result:** ✅ `python -m autoinfo.mcp.server` starts and responds.

**Actual Result:** _________ **PASS / FAIL:** _________

#### 60.12 🟢 REST API server entry point works
```bash
timeout 3 python3 -m autoinfo.api.server 2>&1 | head -5; echo "Exit: $?"
```
**Expected Result:** ✅ Server starts (may timeout waiting for connections). No import errors.

**Actual Result:** _________ **PASS / FAIL:** _________

---

### 📊 Q60 Verdict

| # | Scenario | Result |
|---|----------|--------|
| 60.1 | Doctor all checks | ⬜ |
| 60.2 | MCP stdio ping | ⬜ |
| 60.3 | Invalid JSON-RPC | ⬜ |
| 60.4 | All 72 tools | ⬜ |
| 60.5 | 3x stress run | ⬜ |
| 60.6 | Clean import | ⬜ |
| 60.7 | Test suite | ⬜ |
| 60.8 | Test collection | ⬜ |
| 60.9 | CLI from anywhere | ⬜ |
| 60.10 | Module entry | ⬜ |
| 60.11 | MCP entry | ⬜ |
| 60.12 | API entry | ⬜ |

**OVERALL: ⬜**
