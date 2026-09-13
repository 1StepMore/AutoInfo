"""Error-message audit: D-工-4 evidence for the best-practice review.

Static audit of the MCP error envelope call sites in
``src/autoinfo/mcp/server.py`` against agent-actionable error guidance
(D-工-4 in ``docs/dev/best-practice-review.md``):

- **Actionable messages** — every ``error_response`` / ``error_dict`` message
  should carry a concrete fix hint (use/add/set/configure/install/enable/
  provide/pass/check/supported/see/docs), per the OWASP actionable-error
  model and the MCP spec's agent-readable message guidance.
- **No raw-exception leakage** — ``_error_dict(exc)`` currently builds
  ``message_str = str(exc)``; a message that equals the exception string is
  flagged as raw-leakage (stack-trace / internal detail exposure to agents).
  Both the keyword form (``message=str(exc)``) and the **positional** form
  (``error_response(ErrorCode.X, str(exc), actionable=True)``) are detected —
  a positional ``str(exc)`` message arg is the false-GREEN this audit used
  to miss (T-S-06 / VT-08). Only a bare ``str(<exception-name>)`` is raw;
  ``str(arguments.get(...))`` is not an exception and is ignored.
- **429 Retry-After** — RATE_LIMITED call sites should mention a retry or
  backoff hint.

Run from the project root: ``python3 scripts/error_message_audit.py``

Exit code is **non-zero** when any raw-exception site is present, so the
audit is a real truth gate, not a report. Pass an optional path to audit a
different file (used by the planted-violation test):

    python3 scripts/error_message_audit.py path/to/server.py

Writes a timestamped report to
``validation-runs/coverage/error-message-<date>.json`` (only for the default
``server.py`` target) and prints a summary to stdout. Pure static analysis —
no server imports.
"""

from __future__ import annotations

import ast
import datetime
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "autoinfo" / "mcp" / "server.py"
OUT_DIR = ROOT / "validation-runs" / "coverage"

# Fix-hint markers that make a message agent-actionable. Based on the
# actionable-error model (OWASP): tell the agent WHAT to do next.
HINT_MARKERS: tuple[str, ...] = (
    "use ",
    "use_",
    "add",
    "set",
    "create",
    "configure",
    "install",
    "enable",
    "provide",
    "pass",
    "check",
    "supported",
    "requires",
    "must",
    "see ",
    "docs",
    "run ",
    "try ",
    "retry",
    "re-run",
    "format",
    "valid",
    "missing",
    "expected",
    "either",
    "choose",
    "not found",
)

RETRY_MARKERS: tuple[str, ...] = (
    "retry",
    "backoff",
    "later",
    "throttl",
    "rate limit",
    "429",
    "too many",
)

# Names that denote a caught exception. A ``str(<name>)`` message argument
# using one of these is raw-exception leakage; any other ``str(expr)`` (e.g.
# ``str(arguments.get(...))``) is not an exception and must not be flagged.
_EXC_ARG_NAMES: frozenset[str] = frozenset({"exc", "e", "err", "error", "exception"})


def _is_raw_exc_expr(node: ast.AST) -> bool:
    """True for ``str(<exception-name>)`` — a raw exception message arg."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "str"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id in _EXC_ARG_NAMES
    )


def _message_from_expr(node: ast.AST | None) -> tuple[str, bool]:
    """Return ``(message, raw)`` for a message argument expression.

    Constants keep their literal text so fix-hint checks work; a raw
    ``str(<exc>)`` becomes the ``<str(exc)>`` marker with ``raw=True``;
    every other expression (f-strings, names, attribute calls) yields an
    empty message — the same neutral treatment the audit always applied to
    non-constant keyword messages.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, False
    if node is not None and _is_raw_exc_expr(node):
        return "<str(exc)>", True
    return "", False


def _call_sites(src: str) -> list[dict[str, Any]]:
    """Collect error_response / error_dict / _error_dict / _error_from_exc call nodes.

    Message extraction covers **both** forms:
    - keyword ``message=<expr>``
    - positional ``error_response(code, <expr>, ...)`` (``args[1]``)
    """
    tree = ast.parse(src)
    sites: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = None
        if isinstance(fn, ast.Name):
            name = fn.id
        elif isinstance(fn, ast.Attribute):
            name = fn.attr
        if name not in ("error_response", "error_dict", "_error_dict", "_error_from_exc"):
            continue
        msg = ""
        raw = False
        if name == "_error_dict":
            # _error_dict(exc) — message is str(exc) at runtime (deprecated;
            # any remaining call site is a raw-exception violation).
            arg = node.args[0] if node.args else None
            arg_name = ""
            if isinstance(arg, ast.Name):
                arg_name = arg.id
            msg = f"<str({arg_name or 'exc'})>"
            raw = True
        elif name == "_error_from_exc":
            # _error_from_exc(exc, context) — the context argument carries
            # the agent-facing operation context; the unified message
            # template (helper body) appends the fix hint. A context may be
            # a literal or an f-string (both non-empty); a missing/None
            # context is the violation.
            ctx = node.args[1] if len(node.args) >= 2 else None
            if isinstance(ctx, ast.Constant) and isinstance(ctx.value, str):
                msg = ctx.value
            elif ctx is not None:
                msg = ast.get_source_segment(src, ctx) or ""
        else:
            msg_node: ast.AST | None = None
            for kw in node.keywords:
                if kw.arg == "message":
                    msg_node = kw.value
                    break
            if msg_node is None and len(node.args) >= 2:
                # Positional message arg (the false-GREEN the old audit
                # missed): error_response(ErrorCode.X, str(exc), ...).
                msg_node = node.args[1]
            msg, raw = _message_from_expr(msg_node)
        sites.append(
            {
                "line": node.lineno,
                "call": name,
                "message": msg,
                "raw": raw,
            }
        )
    return sites


def _helper_template_ok(src: str) -> bool:
    """Check the ``_error_from_exc`` helper's message template carries a fix
    hint (the template-level guarantee that replaces per-site hints)."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_error_from_exc":
            texts = [
                n.value
                for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            ]
            joined = " ".join(texts).lower()
            return any(m in joined for m in HINT_MARKERS)
    return False


def audit_errors(src: str) -> dict[str, Any]:
    """Audit every error call site against the D-工-4 conventions.

    Parameters
    ----------
    src:
        Contents of ``src/autoinfo/mcp/server.py``.

    Returns
    -------
    dict
        With keys ``total_sites``, ``summary``, ``violations``
        (``raw_exception``, ``no_fix_hint``, ``rate_limited_no_retry``),
        and ``sites``. Sorted deterministically by line.
    """
    sites = _call_sites(src)
    sites.sort(key=lambda s: s["line"])

    raw_exception = [s for s in sites if s["call"] == "_error_dict" or s["raw"]]
    no_hint = [
        s
        for s in sites
        if s["call"] in ("error_response", "error_dict")
        and s["message"]
        and not any(m in s["message"].lower() for m in HINT_MARKERS)
    ]
    # _error_from_exc sites must pass a non-empty operation context; the
    # fix-hint part is guaranteed by the helper template (checked below).
    from_exc_missing_context = [
        s for s in sites if s["call"] == "_error_from_exc" and not s["message"]
    ]
    helper_template_ok = _helper_template_ok(src)
    # RATE_LIMITED sites should carry a retry/backoff hint; find them by the
    # code argument referencing RATE_LIMITED.
    rate_sites: list[dict[str, Any]] = []
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = (
            fn.id
            if isinstance(fn, ast.Name)
            else (fn.attr if isinstance(fn, ast.Attribute) else "")
        )
        if name not in ("error_response", "error_dict"):
            continue
        code_arg = next((k.value for k in node.keywords if k.arg == "code"), None)
        code_src = (ast.get_source_segment(src, code_arg) if code_arg else "") or ""
        if "RATE_LIMITED" in code_src or "RateLimited" in code_src:
            msg = next(
                (
                    str(k.value.value)
                    for k in node.keywords
                    if k.arg == "message" and isinstance(k.value, ast.Constant)
                ),
                "",
            )
            rate_sites.append(
                {
                    "line": node.lineno,
                    "message": msg,
                    "has_retry_hint": any(m in msg.lower() for m in RETRY_MARKERS),
                }
            )

    rate_limited_no_retry = [s for s in rate_sites if not s["has_retry_hint"]]

    summary = {
        "total_sites": len(sites),
        "raw_exception_sites": len(raw_exception),
        "no_fix_hint_sites": len(no_hint),
        "rate_limited_sites": len(rate_sites),
        "rate_limited_no_retry": len(rate_limited_no_retry),
        "from_exc_sites": sum(1 for s in sites if s["call"] == "_error_from_exc"),
        "from_exc_missing_context": len(from_exc_missing_context),
        "helper_template_ok": helper_template_ok,
    }
    return {
        "total_sites": len(sites),
        "summary": summary,
        "violations": {
            "raw_exception": [s["line"] for s in raw_exception],
            "no_fix_hint": [
                {"line": s["line"], "call": s["call"], "message": s["message"]} for s in no_hint
            ],
            "from_exc_missing_context": [s["line"] for s in from_exc_missing_context],
            "rate_limited_no_retry": [
                {"line": s["line"], "message": s["message"]} for s in rate_limited_no_retry
            ],
        },
        "sites": sites,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:]) if argv is None else list(argv)
    target = Path(args[0]) if args else SRC
    src = target.read_text(encoding="utf-8")
    result = audit_errors(src)
    s = result["summary"]

    print(f"Error-message audit (D-工-4) — {datetime.date.today().isoformat()}")
    print(f"Target: {target}")
    print(f"Total error call sites: {s['total_sites']}")
    print(
        f"Raw-exception sites (_error_dict / str(exc) as message, "
        f"positional or keyword): {s['raw_exception_sites']}"
    )
    print(f"Messages without fix hint: {s['no_fix_hint_sites']}")
    print(
        f"_error_from_exc sites: {s['from_exc_sites']} "
        f"(missing context: {s['from_exc_missing_context']}, "
        f"helper template ok: {s['helper_template_ok']})"
    )
    print(
        f"RATE_LIMITED sites: {s['rate_limited_sites']} "
        f"(no retry hint: {s['rate_limited_no_retry']})"
    )

    v = result["violations"]
    if v["raw_exception"]:
        print(f"\nraw_exception lines: {v['raw_exception'][:30]}")
    if v["no_fix_hint"]:
        print(f"\nno_fix_hint ({len(v['no_fix_hint'])}):")
        for row in v["no_fix_hint"][:12]:
            print(f"  L{row['line']} {row['call']}: {row['message'][:80]}")
    if v["rate_limited_no_retry"]:
        print(f"\nrate_limited_no_retry ({len(v['rate_limited_no_retry'])}):")
        for row in v["rate_limited_no_retry"][:5]:
            print(f"  L{row['line']}: {row['message'][:80]}")

    if target == SRC:
        out_dir = OUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"error-message-{datetime.date.today().isoformat()}.json"
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nWrote {out_path}")

    # Truth gate: a raw-exception site must fail the audit, never report GREEN.
    return 1 if s["raw_exception_sites"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
