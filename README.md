# AutoInfo

**Universal information tracking and knowledge base platform.**

Configure sources and topics. AutoInfo handles the rest: automated collection,
LLM-based structured extraction, summarization, and a queryable knowledge base.

> "AutoInfo is your information assistant — not helping you search, but
> automating the entire pipeline from collection to knowledge curation."
>
> Domain-agnostic. Agent-native. BYOK.

## Features

- **Multi-source collection** — RSS, REST APIs (PubMed E-utilities), web pages
- **LLM-powered extraction** — TL;DR, key points, entity extraction, relevance scoring
- **Knowledge base (Hermes model)** — Markdown files with YAML frontmatter + SQLite index
- **Hybrid search** — Keyword (SQLite) + semantic (via LLM embeddings)
- **Agent-native** — All capabilities as MCP tools. Agent operates, human directs.
- **BYOK** — Bring your own LLM keys. Multi-provider via LiteLLM/OpenRouter.
- **Domain-agnostic** — Not hardcoded to any vertical. Users define their own domains.

## v0.1 Status

| Component | Status |
|-----------|--------|
| Config system | ✅ YAML-based, env var resolution, validation |
| `autoinfo init` | ✅ Creates project skeleton with demo domains |
| PubMed API handler | ✅ esearch + efetch, rate limiting, retry |
| RSS handler | ✅ RSS 2.0 + Atom via feedparser |
| LLM extraction | ✅ LiteLLM integration, TL;DR + key points + entities + relevance (0-100) |
| Quality gates G1-G3 | ✅ Source authority, dedup, relevance scoring (advisory) |
| KB storage | ✅ Markdown files in `knowledge/01-Raw/` + SQLite metadata index |
| CLI commands | ✅ init, doctor, collect, process, status, summaries |
| MCP server | ✅ 6 tools (health_check, diagnose_system, collect_sources, process_collection, list_summaries, get_kb_entry) |
| Test suite | ✅ 220 tests, pytest + VCR cassettes + snapshot regression |
| **Not in v0.1** | No FTS5 search, no Draft/Wiki tiers, no scheduled cron, no web UI |

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Initialize with demo domain
autoinfo init --demo medical-research

# Configure LLM key
export AUTOINFO_LLM_API_KEY="sk-..."

# Collect and process
autoinfo collect --domain medical-research --topic "IVF breakthroughs" --limit 5
autoinfo process --domain medical-research

# Browse results
autoinfo summaries list --domain medical-research
autoinfo status --domain medical-research
```

## Architecture

```
Sources (RSS/API)
        │
        ▼
   autinfo collect ───→ collections/ (raw JSON cache)
        │
        ▼
   autoinfo process
        │
   ├── LLMExtractor (LiteLLM)
   ├── Quality Gates (G1-G3)
   └── KBStore
        │
        ▼
   knowledge/01-Raw/ ────→ Markdown files + SQLite index
        │
        ▼
   autinfo summaries list | autoinfo status | MCP tools
```

## Interface

- **Primary**: MCP tools (`python -m autoinfo.mcp.server`)
- **Fallback**: CLI (`autoinfo <verb> --domain <domain>`)
- **NOT v1**: No web UI, no mobile app, no email delivery

## Demo Domains

| Domain | Validates | Priority |
|--------|-----------|----------|
| **Medical Research** (辅助生殖/脑科学) | Academic paper collection (PubMed), structured metadata | 🔴 P0 — Implemented |
| **AI Commercial Intelligence** | Multi-source collection (API + web + feeds) | 🟡 P1 — Future |
| **Language Learning** (children's English) | Level classification, content simplification | 🟢 P2 — Future |

## CLI Commands

```bash
autoinfo init --demo <domain>       # Initialize project
autoinfo doctor                      # System health check
autoinfo collect --domain <d> ...   # Collect from sources
autoinfo process --domain <d> ...   # LLM extraction + storage
autoinfo collect --auto-process     # Collect + process in one step
autoinfo status                     # Collection stats
autoinfo summaries list             # Browse extracted summaries
```

## MCP Tools (6)

| Tool | Description |
|------|-------------|
| `health_check` | Server health status |
| `diagnose_system` | Comprehensive system diagnostics |
| `collect_sources` | Collect from configured sources |
| `process_collection` | Run LLM extraction + quality gates + storage |
| `list_summaries` | List extracted summaries with pagination |
| `get_kb_entry` | Read full KB entry content |

## Development

```bash
pip install -e ".[dev]"
make test        # pytest -v
make lint        # ruff check + mypy
pytest -v        # 220 tests
```

## Test Strategy

- **Unit tests**: pytest + CliRunner for CLI, VCR cassettes for HTTP
- **LLM extraction**: Snapshot regression with synthetic fixtures — no real LLM calls in CI
- **Quality gates**: Pure Python, no external dependencies
- **Integration**: End-to-end True Test (T1-T5) with temp directory isolation

## License

MIT
