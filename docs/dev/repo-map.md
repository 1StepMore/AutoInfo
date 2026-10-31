# Repo Map — project structure & runtime-artifact boundary

> Loaded on demand from `AGENTS.md` (#671). Source of truth for *what lives where* and
> *what is source vs runtime state*. Runtime state must never be hand-edited to fix
> behavior — fix the source (`src/`).

## Project Structure

```
AutoInfo/
├── AGENTS.md                       # Root agent instruction index (rules + pointers, #671)
├── README.md                       # Project overview + Status table (all counts, single source of truth)
├── pyproject.toml                  # Python packaging
├── Makefile                        # Build automation
├── .gitignore
├── docs/
│   ├── dev/
│   │   ├── founder-expectations.md # Index doc (simplified; full content in specs/)
│   │   ├── specs/                  # Extracted spec files (2026-07-26 restructuring)
│   │   │   ├── expectations.md     # F01-F72 expectation catalog (72 expectations, 16 phases)
│   │   │   ├── quality-gates.md    # G0-G7, D1-D3 gate catalog & configuration + testing strategy
│   │   │   ├── pipeline.md         # Collection pipeline, KB pipeline, LLM config, extraction, search, performance targets
│   │   │   ├── delivery.md         # Output generation, delivery channels, end user lifecycle
│   │   │   ├── operations.md       # Cost, data privacy, knowledge lifecycle, observability
│   │   │   ├── market-positioning.md # Priority matrix, competitive landscape, pricing, personas
│   │   │   ├── mcp-tools.md        # MCP tools catalog (counts in README.md Status table)
│   │   │   ├── data-models.md      # Consolidated data model schemas
│   │   │   ├── user-lifecycle-definition.md # Foundational user type definitions (B1/B2/B3)
│   │   │   ├── multi-tenancy-auth.md    # Multi-tenancy and authorization spec
│   │   │   └── ops-runbook.md           # Operations runbook spec
│   │   ├── cross-dimensional-catalog.md # Cross-dimensional catalog — keystone product matrix (A1-A7 × B1/B2/B3, supersedes archived gap docs)
│   │   ├── repo-map.md             # ← You are here (this file)
│   │   ├── archive/                  # Archived/historical docs
│   │   ├── director-user-guide.md    # Human-Agent interaction lifecycle
│   │   └── plans/                    # Remediation / restructuring plans (decision points)
├── .opencode/
│   └── skills/                     # Agent skills — deep-modules/doc-manager/maintainer-workflow/validation-runner (developing AutoInfo) + autoinfo-skill/translator-qa-skill (operator skills for agent-users of AutoInfo; moved from docs/skills/ 2026-10-30)
├── src/
│   └── autoinfo/
│       ├── cli/                     # 31 CLI command groups
│       ├── mcp/                     # MCP server (149 tools); server.py = hub (app, discovery, _TOOL_DISPATCH, call_tool); context.py = shared helper tier; tools/ = per-domain schemas + handler bodies (_handle_*), one module per domain; _TOOL_DISPATCH = single name→handler dispatch table (#581)
│       ├── api/                     # REST API (FastAPI, port 8741)
│       ├── kb.py                    # Knowledge base pipeline (4-tier KB pipeline)
│       ├── collectors/              # 30 collector handlers (PubMed, Semantic Scholar, DBLP, OpenAlex, USPTO, NYT, Yahoo Finance, Quandl, RSS, Web, webhook, email, PDF, Reddit, Spotify, YouTube, Bilibili, Apple Podcasts, AP API, Reuters MCP, SSRN, GDELT, HuggingFace/Kaggle, Unpaywall/CORE, HackerNews, AKShare, SEC EDGAR, edX sitemap) + registry.py (source_type → Collector lookup; enforced `fetch_items(ctx)` contract)
│       ├── llm.py                   # LLM extraction engine
│       ├── output/                   # Output generation package (digest, report, tutorial, presentation, export; formats: Markdown/HTML/JSON/PDF/Audio/Agent/EPUB/MOBI/Audiobook/Video) — __init__.py (hub + product orchestration) + contracts.py (dependency-free contract types + JSON-LD literals) + audience.py (audience vocabulary) + sources.py (source labelling + drift filtering) + templating.py (Jinja env + product templates) + gates.py (product judge + delivery gates) + report.py (report synthesis internals) + export.py (KB export family: export_kb + all format exporters) + entries.py (shared deterministic entry filters) + grouping.py (thematic grouping: LLM/deterministic/keyword + degradation state) + render.py (report + generic Markdown/HTML/JSON/agent renderers) + tutorial.py + presentation.py + audio.py (product pipelines) + ebook.py (B23: EPUB/MOBI/audiobook) + video.py (HyperFrames HTML+GSAP→MP4, 36+8 themes) + video_assets/ (themes + templates) + seo.py + free_tier.py (free-tier product limits)
│       ├── data/                     # Domain configs (domains/*/sources.yaml) + 8 output product templates (the 8 `*.md.j2` files; `templates/` also holds 3 `*.html.j2` renderer variants — 11 `.j2` in total — incl. premium-briefing.md.j2, enterprise-briefing.md.j2) + prompts/ (16 LLM prompt files, loaded via prompts.py)
│       ├── prompts.py                # Prompt registry + loader (issue #426): PROMPTS_DIR / list_prompts / get_prompt / render_prompt / PROMPT_VERSIONS / PROMPT_PLACEHOLDERS. `$name` placeholders — NOT `{name}` (several prompts carry literal JSON braces). Prompt text is byte-pinned in tests/test_prompts.py.
│       ├── cefr.py                  # CEFR classification (EN/ZH/JA)
│       ├── quality.py               # Quality gates G0-G7, D1-D3 delivery gates
│       ├── delivery.py              # Delivery channel abstraction
│       ├── delivery/scheduler.py    # Delivery schedule management (cron integration)
│       ├── delivery/gate_report.py   # Per-product gate reports (01-QA-GATES/ md+json for validation delivery)
│       ├── delivery/frequency_gate.py # Delivery frequency gate (free-tier frequency enforcement at cron add-delivery)
│       ├── alerts.py                # Alert rule CRUD, YAML persistence, check & dispatch
│       └── ...                      # email_sender, keywords, qa, etc.
```

## Runtime Artifacts vs Source Files

AutoInfo generates runtime state at execution time. Distinguish from source:

| Path | Type | Notes |
|------|------|-------|
| `src/` | **Source** | Code, the only source of truth for behavior |
| `tests/` | **Source** | Test suite |
| `docs/` | **Source** | Documentation |
| `AGENTS.md`, `README.md`, `pyproject.toml`, `Makefile` | **Source** | Project metadata |
| `collections/` | Runtime | Raw JSON cache from `collect`, gitignored |
| `knowledge/` | Runtime | 4-tier KB pipeline output (01-Raw, 02-Draft, 03-Wiki), gitignored |
| `outputs/` | Runtime | Generated digests, reports, exports, gitignored |
| `mvp/` | Runtime | Concierge MVP pilot delivery dirs (`mvp/<user_id>/`: product + gate report + provenance), gitignored |
| `autoinfo.db` | Runtime | SQLite KB + user + cost stores, gitignored |
| `logs/` | Runtime | Structured pipeline logs, gitignored |
| `.autoinfo/` | Runtime | Project config (`config.yaml`), gitignored — modify via MCP tools, not by hand |
| `.omo/` | Runtime | Agent-orchestrator workspace, gitignored (see `AGENTS.md` §`.omo/`) |

Never hand-edit runtime artifacts to fix behavior — fix the source.

The boundary is mechanically guarded: `tests/validation/test_tracked_runtime_artifacts.py`
walks `git ls-files` and fails when any tracked path lives under a runtime directory
(`.omo/` with no exception). Keep this table in sync with `.gitignore`.
