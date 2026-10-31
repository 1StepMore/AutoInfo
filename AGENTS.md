# AutoInfo — Agent Guide

> Root instruction **index** — rules + pointers, not a corpus (#671; adherence ceiling ~200 lines,
> `docs/dev/agent-era-doc-architecture.md` §1). Detail loads on demand: repo layout → `docs/dev/repo-map.md` ·
> LLM setup → `docs/dev/llm-config.md` · gates/pipeline → `docs/dev/specs/` · examples → `docs/dev/mcp-usage-examples.md`.

## What Is AutoInfo

AutoInfo is a **universal information tracking and knowledge base platform**. You configure
sources and topics; AutoInfo handles collection, LLM-based structured extraction,
summarization, and builds a queryable knowledge base. **Domain-agnostic**: the demo domains
(medical-research, ai-commercial, financial-intelligence, …) are configurations, not
hardcoded features — users define their own domains.

## Agent Operating Model

**Agent-first**: the human director communicates intent in natural language → you translate
to MCP tool calls (stdio server). All capabilities are MCP tools (counts: `README.md` →
Status table). CLI mirrors MCP — `--domain X --topic Y` maps 1:1 to tool parameters; humans may use the CLI as a fallback.

## Quick Start & CLI

```bash
python -m autoinfo.mcp.server               # MCP stdio server (agent-facing; never interactive)
autoinfo init --demo medical-research       # scaffold a demo domain
autoinfo collect --domain medical-research  # fetch items (live per-source progress lines)
autoinfo process --domain medical-research  # LLM extraction + quality gates (G4/G5 opt-in — see gates)
```

MCP client configs are committed: `.cursor/mcp.json` (restart Cursor), `.opencode/mcp.json`
(auto-discovered); Claude Desktop: copy `.claude/claude_desktop_config.json` to the path in
`docs/dev/llm-config.md`. CLI entry points (same Typer app, `src/autoinfo/cli/__init__.py`):
`autoinfo <cmd>` (from `pip install -e .` / `make install`) or `python -m autoinfo.cli <cmd>`.
**Do not confuse CLI with MCP server**: `python -m autoinfo.mcp.server` speaks JSON-RPC over
stdio — never interactive.

## Architecture Rules

Hard constraints derived from `docs/dev/founder-expectations.md` (the *why* lives in
`docs/adr/`). Violating them produces incorrect behavior.

### KB Pipeline

`Collected Item → 01-Raw (sole entry, auto-ingest) → 02-Draft (agent processes/creates from
Raw only) → 03-Wiki (agent promotes)`.

| Rule | Why |
|------|-----|
| **01-Raw is the sole entry point** for all collected content | Every collected item must have complete source provenance; no skipping |
| **Agent cannot create Draft from outside** — only from 01-Raw | Prevents garbage entries; Raw→Draft→Wiki is sequential |
| **Agent promotes Draft→Wiki via `promote_kb_draft`** | Production step executed by the agent, no human gate (director decision 2026-08-08; ADR-0002) |
| **03-Wiki is append-only** | Demotion/deletion are not agent operations; tag `status: deprecated` only upon explicit human command |
| **Source metadata is mandatory** | Every Raw entry must have `source_url`, `source_type`, `source_platform` |
| **Product-analysis metadata** | Per-product fields persist in `custom_fields["product_analysis"]`; filterable via `search_knowledge_base(filter_custom_fields=...)` |

Full KB/collection pipeline detail: `docs/dev/specs/pipeline.md` §1–2; rationale:
`docs/adr/0001`, `docs/adr/0002`.

### Collection Pipeline

Two phases, separable in time: `collect` (parallel source handlers → raw JSON cache to
`collections/` → dedup URL→DOI→fuzzy title→semantic → collection log), then `process` (LLM
extraction with per-task model config → quality gates → 01-Raw KB entries). Every handler
implements the `Collector` ABC's `fetch_items(ctx)` contract via `collectors/registry.py` —
adding a source is one class plus one registration, never a dispatch-chain edit.

### Quality Gates

| Gate | Type | Action on failure |
|------|------|-------------------|
| G0: Schema integrity | 🔴 Hard | block (no retry; deterministic check, retrying cannot change the result; item written to `_failed/`) |
| G1: Source authority (tier check) | 🟡 Soft | configurable: archive/flag/pass |
| G2: Dedup (URL + fuzzy title) | 🟡 Soft | configurable: archive/flag/pass |
| G3: Relevance scoring (0-100) | 🟡 Soft | configurable: archive/flag/pass (below threshold) |
| G4: Factual consistency | 🔴 Hard | 3× retry with escalating context → block |
| G5: Translation accuracy | 🟡 Soft | configurable: archive/flag/pass |
| G7: Entity-fact consistency | 🟡 Soft | default flag (deterministic, no LLM); per-domain `block`; honest hedges never flagged |
| D1: Product completeness / D2: Format integrity | 🔴 Hard | block delivery |
| D3: Freshness | 🟡 Soft | configurable threshold |

- **Default activation** — the table says what a gate does *when it runs*; this says *when
  it runs*: G0/G1/G2/G3/G7 run by default at process time; **G4/G5 are opt-in flags** (CLI
  `--check-factual` / `--check-translation`; MCP `check_factual` / `check_translation`,
  default `false`) — G4 additionally runs unconditionally in the Draft→Wiki CurationGate.
  D1-D3 run only where `delivery_gates` is configured — the shipped default config and
  every demo domain set none, so **delivery gates are off by default** (decision point A
  in `docs/dev/plans/agent-infra-remediation-2026-10-30.md`).
- Full gate catalog + configuration + testing strategy: `docs/dev/specs/quality-gates.md`.

### Product QC — 3-Layer Model (issue #194)

- **L0 dead-code gate** (default, blocking): `make validate DIR=outputs/<domain>` (or
  `python3 scripts/quality_gate.py <dir>`) — deterministic structural checks (F1 empty
  shell, F2 placeholders, F3 doubled citations, F4 forbidden words, C1 fake entries, C2
  log leaks, C3 CJK residue, C4 truncated lines, C5 source integrity, C6 narrative
  grounding #192, X1 cross-product entity conflicts). Exit 0/1/2.
- **L1 agent battery** (opt-in `--semantic`): `scripts/agent_review/battery.py` — semantic
  blind-spot judging over residue L0 cannot see; verdicts carry mandatory evidence;
  unreachable/unparseable judgment ⇒ **ESCALATE, never PASS** (#195). Manifest:
  `scripts/agent_review/blindspots.yaml`. Vendor/model-agnostic via `config.llm`
  (structured output capability-probed, else deterministic markdown parsing).
- **ESCALATE (human)**: value/intent calls go to the human director — never machine-final
  for subjective calls.
- **Single-production discipline**: a product is produced ONCE; QC (L0 → opt-in L1 →
  ESCALATE) is the arbiter. No regenerate-and-select ("best of N" reintroduces hidden
  selection bias). A failed gate ⇒ ONE constrained regeneration (defect fed back), re-gate.
- **Honest hedges are PASS**: "not disclosed in the available sources" is CORRECT behavior
  (#179/#191) — never flag it.

## Agent Constraints (MUST NOT)

| Action | Reason |
|--------|--------|
| Run the CLI `init` in agent workflows | Use the `init_project` MCP tool; CLI `init` remains for humans |
| Manage raw API keys | Use `configure_llm()` for BYOK — stores an env-var reference (`${AUTOINFO_LLM_API_KEY}`), never the raw key; never store/generate/transmit keys |
| Demote or delete Wiki entries | 03-Wiki is append-only; `deprecated` tag only upon explicit human command |
| Create Draft from outside 01-Raw | Draft must come from 01-Raw |
| Delete source or domain config | Human decides what sources/domains to remove |
| Modify `.autoinfo/config.yaml` directly | Use MCP tools (`add_source`, `add_topic`) |
| Run `autoinfo doctor` | Use `diagnose_system()` — returns structured health data |

## Merging a PR (MUST)

Each rule exists because its absence produced a specific failure (two agents write here).

| Rule | Why |
|------|-----|
| **Rebase onto the latest `origin/main` before merging** | `strict_required_status_checks_policy: true`; with two writers a stale-base merge can be textually clean yet semantically wrong — the rebase makes CI test the real merge result |
| **Merge with `--squash` only** | The ruleset allows no other merge method |
| **Expect no human approval gate** | `required_approving_review_count` is 0; GitHub forbids self-approval and agents push under the repo owner account — approval lives in the director's instruction |
| **Sign off every commit** | DCO (`Signed-off-by` trailer; `git commit -s`; ADR-0009) |
| **Prefer fewer, larger PRs** | The release PR auto-merges minutes after any push to `main` (ADR-0007), invalidating open PRs — budget ~20 min rebase CI cycle |

## Tool Discovery & Response Format

Discovery: `health_check()` → `tools/list` → `list_domains()` → `get_domain_schema(domain)`
→ `list_available_models()` → `list_output_templates(domain)`. Full catalog with counts:
`README.md` (single source of truth). Validation: `list_validation_scenarios` /
`run_validation_scenario` (contract: `docs/dev/validation-scenario-contract.md`). All tools
return `{success: true, data: ...}` or `{success: false, error: {code, message, actionable}}`
(ADR-0005; codes in `src/autoinfo/mcp/errors.py`). Follow the remediation hint in
`error.message`. `LLM_NOT_CONFIGURED` when no key; `process_collection` with no cached items
returns `{status: "noop"}`. Worked patterns: `docs/dev/mcp-usage-examples.md`.

## LLM Configuration (essentials)

- **Precedence** (highest first): MCP tool parameter → `.autoinfo/config.yaml` `llm.*` →
  `AUTOINFO_LLM_API_KEY` → defaults (openrouter / deepseek/deepseek-chat).
- **Judgment calls** (G4/G5/llm_judge) resolve **config-first** (#195):
  `llm.judgment_model` → `llm.model` → `JudgmentModelNotConfiguredError` — no hardcoded
  model constant; a drifted task override can never change what model judges content.
- **Fallback chain**: `[primary] + llm.fallback` — first success wins, shared per-provider
  limiter + jittered 429/5xx backoff. **A cross-endpoint fallback never inherits the
  primary key** — it must carry its own `${ENV}` reference.
- Full setup (env table, `json_mode`/reasoning controls, custom endpoints, fallback
  example, per-task routing): **`docs/dev/llm-config.md`**.

## `.omo/` Workspace

`.omo/` is the **agent-orchestrator workspace** (Sisyphus-style plans/notepads/evidence/
`boulder.json`) — gitignored runtime scratch, not AutoInfo product data. Agents may **read**
it to recover orchestrator context; never treat it as KB/sources/output, never modify it
from AutoInfo MCP tools (owned by the orchestrator layer above AutoInfo).

## Runtime Artifacts vs Source Files

`src/`, `tests/`, `docs/`, repo metadata are **source** — the only source of truth for
behavior. `collections/`, `knowledge/`, `outputs/`, `mvp/`, `autoinfo.db`, `logs/`,
`.autoinfo/`, `.omo/` are gitignored **runtime state**. Never hand-edit runtime artifacts
to fix behavior — fix the source. Full per-path table: `docs/dev/repo-map.md`.

## Backlog Priority Triggers

某些 P1 项的等级由「该工作量是否继续发生」决定——触发条件命中时**等级自动回升，不需要重新评审**：

| 项 | 当前等级 | 回升触发 | 回升后 |
|:--|:--|:--|:--|
| collectors 层重构（30+ handler / 130+ 源） | P1 | 下一次**加源或加域**（`src/autoinfo/collectors/` 或域配置新增） | P0 |

## Status

Status and **all counts** live in **`README.md` → Status table** (single source of truth;
AGENTS.md is pointer-only). Regenerate: `python3 scripts/doc_inventory.py`; `--check`
validates counts against code/CLI. Invariants: Architecture Rules above +
`docs/dev/acceptance-framework.md` (AC1-AC9).

## References

- `docs/dev/repo-map.md` — repo layout + runtime-artifact boundary · `docs/dev/llm-config.md` — full LLM setup (both loaded on demand)
- `docs/dev/workflow-charter.md` — dev process (canonical methodology: `docs/dev/七阶段AI开发流程-用CodingAgent交付成品的方法论.md`; ADR-0006)
- `docs/dev/mcp-usage-examples.md` — worked MCP patterns · `docs/dev/required-api-keys.md` — API keys/env vars catalog
- `docs/dev/founder-expectations.md` (D3 index) · `docs/dev/specs/` (extracted specs) · `docs/dev/cross-dimensional-catalog.md` (**keystone** matrix A1-A7 × B1/B2/B3) · `docs/dev/enduser-coverage-matrix.md`
- `docs/dev/acceptance-framework.md` — **keystone** acceptance (AC1-AC9); `docs/dev/validation-scenario-contract.md` — scenario contract
- `docs/adr/` — decision records · `docs/glossary.md` — ubiquitous language · `docs/demo-release-standard.md` — demo DoD · `docs/known-limitations/demo-quality-residuals.md` — residual register
- `docs/dev/agent-era-doc-architecture.md` + `-autoinfo.md` — doc-architecture playbook + AutoInfo map (maintenance loop, cleaned-items record)

## Community

`CONTRIBUTING.md` (Conventional Commits, AI policy, mandatory 回归场景) · `GOVERNANCE.md` ·
`CODE_OF_CONDUCT.md` · `SECURITY.md` · `.github/` (templates, CODEOWNERS, release-please workflow gates).
