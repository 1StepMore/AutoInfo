# AutoInfo v1.6 — Gap Analysis & Known Issues [DEPRECATED]

> **This document is DEPRECATED as of 2026-07-26.**
>
> The 2 "BLOCKING" gaps (missing `UserProfile`, `Subscription`, `CostRatesConfig`) identified here
> have been FIXED — `user_store.py` (419 lines), `cost.py`, and `models.py` all work correctly.
> The MCP-layer gaps noted here are now tracked as status markers (🔄) in
> `docs/dev/specs/expectations.md` (F36-F41, F43-F45).
>
> **Current status**: See `docs/dev/specs/expectations.md` for up-to-date per-expectation status markers.
> **Code state**: All 57 expectations documented; 53/57 implemented (✅), 4 partial (🔄), F30 deferred to v2+ (❌).

**Date:** 2026-07-25 (deprecated 2026-07-26)
**Version:** v1.6.0
**Audit method:** Automated codebase import checks + AST analysis + manual file verification
**Scope:** All 57 founder expectations (F01-F57) + 6 GitHub issues

---

## Executive Summary

After the v1.6 gap-fill sprint (3h 8m, 10 tasks completed), a comprehensive audit of all 57 founder expectations against the actual codebase reveals:

- **53/57 expectations documented as ✅** in `founder-expectations.md`
- **42/57 (74%) actually runnable** against codebase
- **2 BLOCKING gaps** that cascade-broke all 22 CLI command groups
- **4 MCP-layer gaps** (backend logic exists but no MCP tool wrappers)
- **9 unimplemented expectations** (full features, not partial)
- **6 GitHub issues** (2 code bugs, 2 test issues, 1 PR pending, 1 new)

**Root causes:** 3 missing class definitions (`UserProfile`, `Subscription`, `CostRatesConfig`) — these were planned in the spec but never added to `models.py` / `config.py`. Fixing them restores ~6 additional expectations to working state.

---

## 🔴 Section 1: BLOCKING — Modules Completely Broken

These 2 gaps cause the entire CLI (`autoinfo` command) to fail at import time because `cli/__init__.py` cascades all 21 submodule imports. A single import failure in any module breaks ALL CLI commands.

| # | Expectation | Doc Status | Actual | Root Cause | Impact |
|---|-------------|:----------:|:------:|-----------|--------|
| **F36** | End User Profile & Subscription CRUD | ✅ | **❌** | `models.py` missing `UserProfile` and `Subscription` dataclasses. `user_store.py` (419 lines), `cli/enduser.py` (185 lines), `cli/portal.py` (149 lines) all import these and fail | 0 MCP tools for end-user. All of F36-F40 broken. Also blocks `cli/trace.py` via cascade |
| **F41-F44** | Cost Governance (metering, dashboard, allocation) | ✅ | **❌** | `cost.py` (467 lines) imports `CostRatesConfig` from `config.py` — class does not exist. `cli/cost.py` (149 lines) cascades the failure | 0 MCP tools for cost. `cli/cost dashboard`, `cli/cost allocation` broken |

### Fix Plan

```python
# 1. Add to src/autoinfo/models.py:

@dataclass
class UserProfile:
    user_id: str
    name: str
    email: str
    status: str = "trial"  # trial → active → suspended → cancelled
    tier: str = "free"
    delivery_preferences: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    # ... (full fields per §12.15)

@dataclass
class Subscription:
    subscription_id: str
    user_id: str
    plan: str = "free"
    status: str = "active"
    # ... (full fields per §12.15)

# 2. Add to src/autoinfo/config.py:

@dataclass
class CostRatesConfig:
    llm_rates: dict[str, float]  # model → $/1K tokens
    storage_rate: float  # $/GB/day
    api_call_rate: float  # $/1K calls
    default_currency: str = "USD"
    # ... (full fields per §12.16)
```

**Estimated effort:** 1-2 hours. Restores ~8 expectations to working state (F36, F38, F40, F41, F43, F44, F55-CLI, trace-CLI).

---

## 🟡 Section 2: MCP Tool Layer Missing (Backend Exists)

These features have working backend logic (Python modules that import and run) but are NOT exposed as MCP tools. The agent cannot access them.

| # | Expectation | Backend | MCP Tool | Missing Tools |
|---|-------------|:-------:|:--------:|---------------|
| **F47** | Data deletion & retention (soft-delete, restore, GDPR export) | ❌ **No backend** | ❌ None | `soft_delete_entry`, `restore_entry`, `export_user_data`, `delete_user_data` — **neither backend logic nor MCP wrappers exist**. This is a complete feature gap, not just MCP layer |
| **F55** | Per-item traceability (trace_id propagation) | ✅ `collect.py:306-311` generates trace_id, assigns to items | ❌ `trace_item` MCP tool missing | `trace_item(trace_id)` — CLI `autoinfo trace` blocked by cascade |
| **F56** | Enhanced diagnostics (doctor --verbose, health score) | 🟡 `diagnose_system()` MCP works. But `doctor.py` has **no verbose mode, no health score, no error rate, no latency p95/p99** | ❌ `doctor --verbose` CLI broken | Verbose flag, health score calculation, error rate tracking, latency percentiles |
| **F57** | Metrics export (Prometheus) | ✅ `/metrics` endpoint works, `metrics.py` `get_metrics()` + `format_prometheus()` functional | ❌ `get_metrics` MCP tool missing | `get_metrics(domain=None)` — agent cannot programmatically fetch metrics |

---

## 🔵 Section 3: Fully Unimplemented

| # | Expectation | Actual Status | Details |
|---|-------------|:------------:|---------|
| **F04** | LLM fallback chain | ❌ Not wired | `config.py:37` parses `llm.fallback` but `llm.py:265` `_call_llm()` only uses `self._model`. `extract_with_retry()` retries same model. Fallback list never consulted |
| **F19** | Cross-ref relation types | ❌ No enum | No `RELATION_TYPES` enum or `RelationType` class anywhere. Relationships use free-form strings (`"related"`, `"related_to"`). No type safety |
| **F49** | Per-domain TTL & freshness scoring | ❌ Not implemented | `DomainConfig` has no `ttl_days` field. No freshness score computation in `kb.py`. No search demotion logic. No stale archival |
| **F50** | Versioned re-collection | 🟡 Partial | `get_entry_history` / `restore_entry_version` MCP tools exist. But **no automatic version bump** on same source_url, no `version`/`previous_version`/`supersedes` frontmatter fields, no `compare_versions` MCP tool |
| **F51** | Stale content handling | ❌ Not implemented | No stale marking, no search demotion, no digest exclusion. `kb.py` has zero references to "stale" or "freshness" |
| **F52** | Domain decay metrics | ❌ Not implemented | No `get_domain_decay` MCP tool. No decay/freshness computation functions in `kb.py`. No grade calculation (Green/Yellow/Red) |
| **F53** | Cross-collection dedup & merge | ❌ Not implemented | `quality.py:275` has `class G2Dedup` (URL/PMID/DOI dedup at collection time) but **no `find_similar_items()`** (TF-IDF/Jaccard), **no `merge_items()`** (LLM-assisted consolidation), **no `merge_items` MCP tool** |
| **F45** | Budget alerts & cost control | 🟡 Partial | `alerts.py` works (rule CRUD, YAML persistence). But **no cost/budget triggers** — no spend threshold evaluation, no auto-remediation actions (pause collection, switch LLM model), no budget alert integration |
| **F42** | External billing model | ❌ **Deferred to v2+** | Entire F42 (Stripe, invoicing, pricing tiers, usage metering) explicitly scoped out. Tracked as future work |

---

## 🐛 Section 4: GitHub Issues

### Open Issues

| Issue | Type | Severity | Status | Description |
|-------|------|:--------:|:------:|-------------|
| **#33** | Code bug | 🔴 P0 | ✅ Fixed (PR #36) | KB count mismatch false warning — `count_entries()` returned wrong count vs actual directory listing |
| **#34** | Test outdated | 🟡 P1 | 🔴 Pending | MCP test asserts `tools_count == 65` but actual count is now 79 |
| **#35** | Test outdated | 🟡 P1 | 🔴 Pending | `generate_presentation` test expects real LLM output but receives mock HTML |
| **#36** | PR | — | 🟡 Pending merge | KB count mismatch fix PR (resolves #33). Awaiting review |
| **#37** | Code bug | 🔴 P0 | 🆕 New | `--raw-id` parameter truncates long IDs silently |
| **#38** | Code bug | 🟡 P1 | 🆕 New | `--json` output format inconsistency across CLI commands — some return dict, some return list, some return string |

### Issue-to-Expectation Cross-Reference

| Issue | Related Expectation | Impact |
|-------|-------------------|--------|
| #33 / #36 | F21 (KB search) | False warnings degrade user trust |
| #34 | F12 (MCP tools) | Test suite blocks CI gate |
| #35 | F25 (Presentations) | Test suite blocks CI gate |
| #37 | F08 (CLI flags) | Data loss on long IDs |
| #38 | F02 (CLI output) | Agent parsing failures |

---

## 📊 Section 5: Coverage Matrix

### By Severity

| Severity | Count | Items | Fix Effort |
|:--------:|:-----:|-------|:----------:|
| 🔴 **BLOCKING** | 2 | F36 (3 missing classes), F41 (1 missing class) | 1-2 hours |
| 🔴 **P0 Bugs** | 3 | #33/#36 (fixed, pending merge), #37 (new) | 30 min |
| 🟡 **MCP Layer** | 3 | F55 (trace_item), F56 (doctor --verbose), F57 (get_metrics) | 2-4 hours |
| 🟡 **P1 Bugs** | 2 | #34 (test count), #38 (--json inconsistency) | 1-2 hours |
| 🟡 **Test Issues** | 2 | #35 (presentation mock), #34 (tool count) | 30 min |
| 🔵 **Unimplemented** | 8 | F04, F19, F49, F50, F51, F52, F53, F45 | 1-2 weeks |
| ⚪ **Deferred** | 1 | F42 (billing → v2+) | N/A |

### By Category

| Category | Expectations | Status |
|----------|:------------:|--------|
| Setup & Config (F01-F06) | 6 | ✅ 5/6 (F04 🟡) |
| Domain & Sources (F07-F10b) | 5 | ✅ 5/5 |
| Collection & Processing (F11-F15) | 5 | ✅ 4/5 (F13 ✅ now) |
| KB Pipeline (F16-F23) | 8 | ✅ 6/8 (F19 ❌, F20 partial) |
| Output & Delivery (F24-F29) | 6 | ✅ 6/6 |
| Product & Billing (F30, F42) | 2 | ⚪ 0/2 (both deferred) |
| **End User Lifecycle (F36-F40)** | 5 | **🔴 0/5** (blocked by F36) |
| **Cost Governance (F41-F45)** | 5 | **🔴 1/5** (alerts only) |
| Data Privacy (F46-F48) | 3 | ✅ 2/3 (F47 ❌) |
| Knowledge Lifecycle (F49-F53) | 5 | **🔵 1/5** (G2 dedup only) |
| Observability (F54-F57) | 4 | 🟡 1/4 (logging only) |

---

## 🎯 Section 6: Priority Fix Roadmap

### Wave 1: Restore Functionality (2-3 hours)
- [ ] Add `UserProfile` + `Subscription` to `models.py` → unblocks F36-F40, F55-CLI
- [ ] Add `CostRatesConfig` to `config.py` → unblocks F41-F44
- [ ] Merge PR #36 → resolves #33
- [ ] Fix #37 (--raw-id truncation)

### Wave 2: MCP Tool Layer (3-4 hours)
- [ ] Register `trace_item` MCP tool → F55
- [ ] Register `get_metrics` MCP tool → F57
- [ ] Add `doctor --verbose` with health score → F56
- [ ] Fix #34 (MCP test tool count)
- [ ] Fix #35 (presentation mock test)
- [ ] Fix #38 (--json inconsistency)

### Wave 3: Feature Completion (1-2 weeks)
- [ ] F04: Wire LLM fallback chain into `_call_llm()`
- [ ] F19: Define `RELATION_TYPES` enum
- [ ] F47: Implement soft-delete, restore, GDPR export (backend + MCP)
- [ ] F49: Add `ttl_days` to `DomainConfig` + freshness scoring
- [ ] F50: Automatic version bump on same source_url + `compare_versions`
- [ ] F51: Stale content search demotion + digest exclusion
- [ ] F52: `get_domain_decay` MCP tool + grade calculation
- [ ] F53: `find_similar_items` + `merge_items` (LLM-assisted)
- [ ] F45: Cost/budget triggers in alerts + auto-remediation

### Wave 4: v2.0+ (Deferred)
- [ ] F30: Subscription & billing infrastructure (Stripe)
- [ ] F42: External billing model (invoicing, pricing tiers)

---

## Appendix: Audit Commands

```bash
# Check model classes
python3 -c "from autoinfo.models import UserProfile, Subscription"  # ❌ ImportError

# Check config classes
python3 -c "from autoinfo.config import CostRatesConfig"  # ❌ ImportError

# Check CLI cascade failure
python3 -c "from autoinfo.cli import collect"  # ❌ ImportError (cascades from enduser/portal)

# Check MCP tool registration
grep 'name="create_end_user\|name="get_cost_report\|name="trace_item\|name="get_metrics"' \
  src/autoinfo/mcp/server.py  # (0 matches)

# Check backend logic
grep -r "trace_id" src/autoinfo/collect.py  # ✅ Found
grep -r "def get_metrics" src/autoinfo/metrics.py  # ✅ Found
grep -r "/metrics" src/autoinfo/api/server.py  # ✅ Found
```

---

## References

- [`founder-expectations.md`](./founder-expectations.md) — Full 57-expectation specification
- [`kb-pipeline-reference.md`](./kb-pipeline-reference.md) — KB pipeline architecture
- [`director-user-guide.md`](./director-user-guide.md) — Human-agent interaction lifecycle
- [`autoinfo-validation-master-plan/`](../autoinfo-validation-master-plan/) — 96-question validation plan
