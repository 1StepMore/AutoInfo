# AutoInfo v0.1 — Learnings

## Project Structure
- `src/autoinfo/` organized as: cli/, collectors/, mcp/, data/ + flat modules (config.py, models.py, collect.py, process.py, kb.py, llm.py, quality.py, status.py, doctor.py, dedup.py)
- CLI uses typer with `--json` global flag via callback
- All core logic is callable Python functions; CLI and MCP are thin wrappers

## Key Architecture Decisions
- Two-phase pipeline (collect → process) with `--auto-process` convenience flag
- PubMed via E-utilities esearch+efetch (not RSS)
- KB storage: Markdown files + SQLite metadata index (no FTS5 in v0.1)
- LiteLLM for multi-provider LLM access; snapshot regression tests mock LLM
- Quality gates are advisory (never block/discard content)
- CLI init is a direct function call (not typer sub-app) because it's a single-command module

## Gotchas Encountered
- **CLI init wiring**: `autoinfo init` broke because cli/__init__.py had a stub raising NotImplementedError. Fix: import function directly, use `app.command()(init_func)`.
- **Config format mismatch**: Init wrote `config["domains"] = [domain_name]` (list of strings) but config.py expected list of dicts. Fix: load sources.yaml at generation time.
- **cli.py vs cli/ package collision**: cli.py clashed with cli/__init__.py. Fix: delete cli.py.
- **pytest-vcr not installed**: RSS test failed because vcrpy was missing.

## Verified Working
- All 220 tests pass
- `autoinfo init --demo medical-research` creates valid config
- `autoinfo doctor`, `autoinfo status`, `autoinfo summaries` all functional
- MCP server starts with 6 tools
- Scope compliance: 15/15 Must NOT Have guardrails respected
