<!-- doc-type: adr -->
# 0005. Unified `{success, data}` / `{success, error}` envelope

- **Status**: Accepted
- **Date**: 2026-08-05 (v1.9, breaking change; migration documented in `docs/archive/migration-v1.9.md`)
- **Author**: Agent (Sisyphus) + Director (B3)

## Context

AutoInfo exposes three surfaces: MCP tools (agent-facing), REST API
(human/agent HTTP), and CLI. Early on, MCP tools returned flat structs and
REST returned raw JSON with opaque error bodies — an LLM agent had to guess
whether a response was data or an error, and error messages carried no
remediation hint. `LLM_NOT_CONFIGURED` surfaced as raw auth errors at the
call site instead of being a first-class signal. The agent-native model (B2)
made unambiguous envelopes a correctness requirement, not a nicety.

## Decision

Every MCP tool and REST endpoint returns the **same envelope**:

- Success: `{success: true, data: ...}`
- Failure: `{success: false, error: {code, message, actionable}}`

`error.code` comes from the `ErrorCode` enum (26 values); every enum *value*
follows one **CamelCase** convention (the enum member name stays
SCREAMING_SNAKE), and every retained code is emitted somewhere. Codes never
emitted are removed rather than left dead: `AuthRequired`/`SessionExpired`
(no auth path yet), `RateLimited` (no emitting surface), and `NoCachedItems`
(a `{status: "noop"}` success, not an error). `message` carries the
remediation guidance; `actionable` flags that a hint exists. The LLM guard
centralizes `LLM_NOT_CONFIGURED` at `call_tool` dispatch, and
`_handle_process_collection` emits `PROCESSING_FAILED` on a processing-run
failure. `error_dict()` is deprecated. Dashboard JS unwraps the envelope
transparently.

## Addendum — text-format payloads are self-describing (2026-09-13, T-S-09)

The envelope answers *"is this data or an error?"*, but a second ambiguity
remained: within a success ``data`` object, some tools returned raw text
(Prometheus exposition text, RSS XML) under an opaque key an agent could not
route without sniffing the bytes.  The rule is now: **no tool returns an
unlabelled raw-text payload.**

- ``get_prometheus_metrics`` → ``data`` = ``{format, content_type, encoding,
  length, bytes, metrics_text}``; ``content_type`` =
  ``text/plain; version=0.0.4; charset=utf-8``.
- ``get_feeds(format="rss")`` → ``data`` = ``{domain, format, content_type,
  encoding, length, bytes, content, pagination}``; ``content_type`` =
  ``application/rss+xml; charset=utf-8``.
- ``length`` is the character count and ``bytes`` the UTF-8 encoded size, so
  a consumer can pre-allocate / verify truncation without decoding twice.

**Intentional exception:** ``health_check`` returns ``data`` as a structured
object (``status`` / ``version`` / ``tools_count``) — there is no text
payload to label, so it carries no text-metadata block.  The same holds for
every JSON-structured tool (``get_feeds(format="json")``, ``get_metrics``,
...).  The metadata requirement applies only where the payload *is* text.

## Alternatives considered

- **Keep flat success + ad-hoc error bodies**: rejected — LLM consumers cannot
  reliably distinguish data from errors; the whole point of agent-native is a
  parseable contract.
- **Error codes only (no message)**: rejected — machine codes without
  human/agent-readable remediation guidance fail the `actionable` goal that
  makes the envelope self-healing.
- **HTTP status codes as the only signal (REST-only)**: rejected — MCP has no
  HTTP, and the two surfaces must share one contract per the CLI/MCP/REST
  parity principle.

## Consequences

- One parse rule for all consumers: read `success`, branch on `data`/`error`.
- All 146 MCP tools and all REST endpoints follow the same schema (validated
  by validation scenarios asserting `{success, data}`); validation
  error-boundary scenarios assert `actionable` presence.
- Breaking change for v1.8 consumers — migration path documented and shipped
  with the v1.9 archive note (dashboard unwrapping transparent).
- Text-format tool payloads (``get_prometheus_metrics``, ``get_feeds`` RSS)
  additionally carry ``format``/``content_type``/``encoding``/``length``/
  ``bytes`` metadata beside the text (T-S-09, 2026-09-13); ``health_check``'s
  structured ``data`` is the documented exception.
