# LLM Configuration

> Loaded on demand from `AGENTS.md` §LLM Configuration (essentials) (#671). Full setup
> reference: config table, precedence, custom endpoints, fallback chains, per-task routing,
> reasoning-model controls. The essentials (precedence, judgment-model rule, cross-endpoint
> key rule) stay in `AGENTS.md`; this doc carries the detail.

AutoInfo uses LiteLLM under the hood. Standard OpenAI-format providers work.

## Config table

| Config | Default | Notes |
|--------|---------|-------|
| provider | openrouter | Use "openai" for OpenAI-compatible endpoints |
| model | deepseek/deepseek-chat | Any LiteLLM-supported model |
| base_url | (none) | Required for non-OpenRouter endpoints |
| api_key | ${AUTOINFO_LLM_API_KEY} | Set via env var or config. The env var may alternatively live in the user-level `~/.autoinfo/.env` file (KEY=VALUE, loaded at CLI/MCP startup with setdefault semantics — a real process environment variable always wins; issue #847). The file is UTF-8; never commit it. |
| json_mode | False | `response_format={"type":"json_object"}` sent only when `json_mode` is True AND `reasoning_model` is False (reasoning providers reject the param). |
| reasoning_model | False | Mark the model as a reasoning model (DeepSeek R1/V4 style). When True: (1) `response_format` is always skipped, (2) chain-of-thought is disabled by default via `additional_body={"thinking":{"type":"disabled"}}` — reasoning consumes the shared `max_tokens` budget *before* content, so leaving it on truncates JSON output (finish_reason=length). Judgment gates (G4 factual, G5 translation, llm_judge, translation QA judge, validation-scenario judge) re-enable thinking with raised `max_tokens` via `disable_thinking=False`. |
| fallback | [] | Ordered `llm.fallback` list — each entry: `model` (required), optional `provider`/`base_url`/`api_key`. An empty `provider` inherits the primary provider; an empty `api_key` inherits the primary key (or its resolved `${ENV}` reference) **only when the fallback targets the same `base_url` as the primary** — a cross-endpoint fallback must carry its own explicit `${ENV}` key (one vendor's key is never transmitted to another vendor's gateway). Every LLM call path (extraction, validation judge, quality gates, translation QA, output generation, keyword suggest, Q&A, CEFR) walks `[primary] + fallback` via `llm.call_with_fallback`; the first successful model wins. Every chain entry runs under the same per-provider limiter and 429/5xx backoff (below). |
| max_concurrency | 4 | Per-provider shared rate limiting: `AUTOINFO_LLM_MAX_CONCURRENCY` env override (clamped ≥1, unparsable → default) bounds in-flight requests per `(provider, base_url)` via a shared `threading.Semaphore` in `call_with_fallback` (llm.py `_PROVIDER_SEMAPHORES`). Enforced across **every** fan-out path — process workers, post-extraction gates, cefr_batch, output grouping, MCP `to_thread` handlers, fallback chain. No single global process-wide lock. |
| 429/5xx backoff | 3 attempts (2 retries) | Jittered exponential backoff on HTTP 429 and 5xx inside `call_with_fallback`: base 1.0s, factor 2, cap 8s, jitter ±25% (llm.py `MAX_LLM_ATTEMPTS`/`BACKOFF_*`). Non-retryable 4xx (400/403/404) surface immediately — never retried. After the final attempt the last error surfaces. |

## Precedence (highest to lowest)

1. MCP tool parameter (e.g. `init_project(llm_provider="openai")`)
2. Config file `.autoinfo/config.yaml` → `llm.provider`, `llm.model`
3. Environment variable `AUTOINFO_LLM_API_KEY`
4. Default values (openrouter/deepseek/deepseek-chat)

## No key at all (three-step ladder)

The precedence chain above answers "which config wins"; it does not answer "what if every rung
is unavailable". That case is the agent/harness ladder (issue #980, implemented in code by
`scripts/agent_ready.py --json` — it probes and reports every step, no vendor hardcoding):

1. **Harness default model** — the agent runtime/harness's own default model, if it has one
   (`agent_ready.py` ladder step 1, probe `harness-default`).
2. **Local OpenAI-compatible endpoint (read-only)** — an endpoint already present on this
   machine, used read-only: `provider="openai"` + `base_url` + model via `.autoinfo/config.yaml`
   or `configure_llm()`, the key referenced as `${ENV}` only (BYOK — never store the raw key).
   Ladder step 2, probe `machine-endpoint`.
3. **Ask the human** — nothing usable on steps 1–2 ⇒ report `blocked:no-llm-key` to the human in
   front of the screen with the **base_url + key + model name** you need; whether it is free is
   their call. Never hardcode a vendor or a free quota. Ladder step 3, probe `ask-human`.

Views of the same ladder: machine — `python scripts/agent_ready.py --json` →
`checks[llm].ladder` / `blocked:no-llm-key`; human — `autoinfo doctor` →
`❌ LLM: no API key configured` plus actionable hints; MCP — LLM-required tools return
`LLM_NOT_CONFIGURED` (ADR-0005 envelope, `actionable` set).

Boundary: this ladder is for **whoever must do judgment work when no key is configured**
(agents / harnesses / QC batteries). AutoInfo's own extraction pipeline still needs a key
configured via the precedence chain above — the ladder invents no credentials, and fake/mock
models are allowed only for chain/contract/coverage testing (`confidence=mock`;
`docs/dev/cross-audit-evidence.md`).

## Custom endpoint

Custom OpenAI-compatible endpoints (e.g. OpenCode Go, Ollama, Azure): set
`provider="openai"`, `base_url` to your endpoint, `api_key` via env var, `model` to your
model name.

## Fallback example

When the fallback sits on the **same gateway** as the primary, empty `provider`/`api_key`
inherit the primary provider/key. The entry below carries full fields with empty
`provider`/`api_key`; because its `base_url` equals the primary's, an empty `api_key`
inherits the primary key (or its resolved `${ENV}` reference). A **cross-endpoint** fallback
(different `base_url`) does NOT inherit the key and must carry its own explicit `${ENV}`
reference — keys are never shared across gateways:

```yaml
llm:
  provider: openai
  model: deepseek-v4-flash
  base_url: https://opencode.ai/zen/go/v1
  fallback:
    - provider: ''
      model: mimo-v2.5
      base_url: https://opencode.ai/zen/go/v1
      api_key: ''
```

## Per-task model routing

`_resolve_task_llm_config` (config.py) resolves the model per task and feeds
`call_with_fallback(task=)` → `_build_config_with_model` (process.py).
Extraction/classification tasks use the task-config model (else the base model).

Judgment calls (G4 factual, G5 translation, llm_judge — the `JUDGMENT_TASKS` frozenset,
config.py) are exempt from task overrides and resolve **config-first** (issue #195,
2026-09-03): `llm.judgment_model` → `llm.model` (provider-qualified) →
`JudgmentModelNotConfiguredError`, raised loudly at the first judgment attempt. The shipped
default is the `llm.judgment_model: openai/deepseek-v4-flash` line in `default_config.yaml`
— a deployment-editable config value, **not** a code constant. There is no
`JUDGMENT_MODEL` constant in the codebase; it was retired in #195 so an unconfigured
deployment can never silently call a guessed model (the #127 ghost-model failure mode).
A drifted `llm.tasks[<name>].model` entry can never change what model judges content.

## MCP client config paths (Claude Desktop)

Copy the committed `.claude/claude_desktop_config.json` to:

- **Linux**: `~/.config/Claude/claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Manual (any platform): run `python -m autoinfo.mcp.server` as the MCP server command.
