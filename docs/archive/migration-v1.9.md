# Migration Note — v1.9 REST Envelope

> Scope: AutoInfo v1.9+ REST API consumers. Landed as part of the M1 REST envelope
> work (M1T11) alongside the dispatch-level audit hook (M1T15). This file records the
> contract change and the migration steps; it does not replace `docs/dev/specs/delivery.md`.

## What changed

All REST success responses are now wrapped in the canonical envelope:

```json
{ "success": true, "data": ... }
```

**Consumers must unwrap `response.data` instead of reading the response body directly.**

Error responses and `/health` are unchanged:

- Errors keep the canonical shape `{success: false, error: {code, message, actionable}}`
  (same envelope the MCP tools return; `actionable` is a boolean, the guidance lives in `message`).
- `/health` remains a flat payload by design — liveness probes and load balancers
  depend on it.
- FastAPI request-validation failures now return **422** with the canonical error
  envelope (`code: "VALIDATION_ERROR"`) via the `RequestValidationError` handler
  added in M1T11 (previously a bare Pydantic 422 body).

## Affected endpoints

| Endpoint | Before (raw) | After (envelope) |
|----------|--------------|------------------|
| `GET /api/v1/entries` | bare list | `{success: true, data: [...]}` |
| `GET /api/v1/entries/{id}` | bare entry dict | `{success: true, data: {...}}` |
| `POST /api/v1/entries` | bare entry dict | `{success: true, data: {...}}` |

The web dashboard (`/dashboard`) already unwraps via an `unwrap(data)` helper and is
backward-compatible.

## Exception: Stripe webhook success path

`handle_webhook()` (Stripe integration) still returns a raw dict (`{status, action, ...}`)
and is **not** enveloped on success. It is an integration contract — Stripe only checks
the 2xx status. Only the Stripe webhook *error* paths were enveloped
(`400` + `VALIDATION_ERROR`). Do not unwrap `data` on webhook success responses.

## Migration checklist

1. Find every REST client that reads the response body directly.
2. On success, unwrap: `payload = response.json(); data = payload["data"]`.
3. Keep error handling on the `{success, error}` shape — unchanged.
4. Keep health checks reading `/health` flat.

## References

- M1T11 — `src/autoinfo/api/routes.py` `_success_envelope` / `_error_envelope`,
  `RequestValidationError` → 422 handler, dashboard `unwrap()`.
- M1T12 — dispatch `TypeError` → `VALIDATION_ERROR` mapping
  (`src/autoinfo/mcp/server.py` `call_tool`).
- Envelope spec: `docs/dev/specs/operations.md` §4, `AGENTS.md` "Response format".
