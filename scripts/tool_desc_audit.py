"""Tool description audit: D-工-1 evidence for the best-practice review.

Static audit of the MCP tool declarations in ``src/autoinfo/mcp/server.py``
against agent-facing tool-design conventions (D-工-1 in
``docs/dev/best-practice-review.md``):

- **Verb-first naming** — the tool's first underscore segment should be an
  action verb (``get_``, ``list_``, ``add_``, ...). Domain-prefixed names
  (``enduser_``, ``cost_``, ``cefr_``) are recorded as namespace-style, not
  verb-first.
- **Parameter count <= 8** (AWS) / <= 5 (Grizzly Peak) — flag tools whose
  inputSchema declares more properties than the guidance thresholds.
- **enum + default coverage** — finite-value parameters should declare an
  ``enum`` and a sensible ``default``.
- **Description quality** — description word count (>= 40 words correlates
  with agent selection accuracy per Anthropic guidance) and explicit
  "when to use" + example markers.

Run from the project root: ``python3 scripts/tool_desc_audit.py``

Writes a timestamped report to ``validation-runs/coverage/tool-desc-<date>.json``
and prints a summary table to stdout. Pure static analysis — no imports of
the server module, so it runs without an LLM key or live config.
"""

from __future__ import annotations

import ast
import datetime
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src/autoinfo/mcp/server.py"
OUT_DIR = ROOT / "validation-runs" / "coverage"

# Action verbs that make a tool name verb-first. Covers get/list/add/remove
# and the mutation + query verbs used across the MCP surface.
VERBS: frozenset[str] = frozenset(
    {
        "activate",
        "add",
        "approve",
        "archive",
        "batch",
        "calculate",
        "check",
        "classify",
        "clean",
        "collect",
        "compare",
        "configure",
        "cost",
        "create",
        "deactivate",
        "delete",
        "demote",
        "diagnose",
        "export",
        "extract",
        "find",
        "flag",
        "force",
        "generate",
        "get",
        "import",
        "init",
        "link",
        "list",
        "localize",
        "mark",
        "merge",
        "process",
        "promote",
        "query",
        "rate",
        "recommend",
        "reindex",
        "reject",
        "remove",
        "restore",
        "run",
        "search",
        "send",
        "set",
        "simplify",
        "soft_delete",
        "suggest",
        "test",
        "trace",
        "update",
    }
)

# Namespace prefixes: "namespace + verb" names (enduser_create, cefr_batch,
# knowledge_graph_export) are industry-accepted agent tool shapes; the audit
# records them as namespace-style rather than verb-first violations.
NAMESPACE_PREFIXES: frozenset[str] = frozenset(
    {
        "cefr",
        "cost",
        "email",
        "enduser",
        "health",
        "knowledge",
        "soft",
        "topic",
    }
)

# Marker phrases that show a description teaches *when* to call the tool.
WHEN_MARKERS: tuple[str, ...] = (
    "when",
    "use ",
    "for ",
    "return",
    "returns",
    "optional",
    "e.g.",
    "example",
    "format",
    "supported",
    "requires",
    "must",
)

# Sanctioned >8-param exemptions (D-工-1: AWS recommends <=8, Grizzly Peak
# <=5). Splitting any of these four would change the public tool surface and
# break existing callers, so they are documented exemptions rather than
# fixable violations. The D-工-1 regression test pins exactly this set
# (tests/validation/test_tool_desc_audit.py::test_over_8_params_are_the_known_heavy_tools).
OVER_8_PARAM_EXEMPTIONS: dict[str, str] = {
    "add_source": (
        "Type-specific convenience params (imap_server/port/username/"
        "password/mailbox, webhook_secret) are mutually exclusive "
        "alternatives, not combinations; the enum'd `type` selects which "
        "group applies."
    ),
    "search_knowledge_base": (
        "One query string plus orthogonal facet filters (domain/mode/tier/"
        "tags/date/custom_fields) plus pagination. The facets are "
        "independent and collapsing them into one object is a breaking "
        "change."
    ),
    "generate_digest": (
        "Independent output knobs: domain/period/format/product/language/"
        "audience/with_references/persist. Grouping knobs into a `filters` "
        "object is a deferred breaking change."
    ),
    "generate_report": (
        "Same output-knob family as generate_digest plus report_type and "
        "domains for cross-domain synthesis; a `filters` object is a "
        "deferred breaking change."
    ),
}


def _tool_calls(server_src: str) -> list[ast.Call]:
    """Return the ``Tool(...)`` call nodes inside ``list_tools()``."""
    tree = ast.parse(server_src)
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id == "Tool":
            calls.append(node)
    return calls


def _kw(call: ast.Call, name: str) -> ast.AST | None:
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def _output_schema_mechanism(server_src: str) -> bool:
    """Return whether ``_full_tool_list`` attaches an outputSchema to every tool.

    The canonical envelope is attached at runtime by
    ``_with_output_schema(...)`` around the tool list; an explicit
    ``outputSchema=`` keyword also counts.  This is the static mirror of the
    runtime 100%-coverage test in ``tests/mcp/test_tool_output_schema.py``.
    """
    tree = ast.parse(server_src)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == "_full_tool_list"):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and isinstance(child.value, ast.Call):
                fn = child.value.func
                if isinstance(fn, ast.Name) and fn.id == "_with_output_schema":
                    return True
    return False


def _str_literal(node: ast.AST | None) -> str:
    if node is None:
        return ""
    # description=( "a" "b" ) — concatenated string constants
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
        return "".join(parts)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    try:
        val = ast.literal_eval(node)
        return val if isinstance(val, str) else ""
    except (ValueError, SyntaxError):
        return ""


def _schema_dict(node: ast.AST | None) -> dict[str, Any]:
    if node is None:
        return {}
    try:
        val = ast.literal_eval(node)
        return val if isinstance(val, dict) else {}
    except (ValueError, SyntaxError):
        return {}


def audit_tools(server_src: str) -> dict[str, Any]:
    """Audit every declared Tool against the D-工-1 conventions.

    Parameters
    ----------
    server_src:
        Contents of ``src/autoinfo/mcp/server.py``.

    Returns
    -------
    dict
        With keys ``declared`` (tool count), ``summary`` (aggregate metrics),
        ``violations`` (verb-first / param-count / short-description lists),
        and ``tools`` (per-tool rows). Sorted deterministically.
    """
    rows: list[dict[str, Any]] = []
    # T-S-01: every declared Tool must carry an outputSchema.  Statically
    # the schema is attached by ``_with_output_schema`` in
    # ``_full_tool_list``; an explicit ``outputSchema=`` keyword also
    # counts (future per-tool refinement).
    output_schema_wrapped = _output_schema_mechanism(server_src)
    for call in _tool_calls(server_src):
        name = _str_literal(_kw(call, "name"))
        if not name:
            continue
        desc = _str_literal(_kw(call, "description"))
        schema = _schema_dict(_kw(call, "inputSchema"))
        props = schema.get("properties", {})
        if not isinstance(props, dict):
            props = {}
        has_output_schema = output_schema_wrapped or _kw(call, "outputSchema") is not None

        first_seg = name.split("_", 1)[0]
        verb_first = first_seg in VERBS
        # namespace+verb: prefix + an action verb in a later segment
        # (enduser_create → enduser + create; soft_delete_entry →
        # soft + delete). email_config has no verb segment → violation.
        tail_segs = name.split("_")[1:]
        namespace_verb = (
            not verb_first
            and first_seg in NAMESPACE_PREFIXES
            and any(seg in VERBS for seg in tail_segs)
        )
        param_count = len(props)
        words = len(desc.split())
        enum_params = [p for p in props.values() if isinstance(p, dict) and "enum" in p]
        default_params = [p for p in props.values() if isinstance(p, dict) and "default" in p]

        rows.append(
            {
                "name": name,
                "verb_first": verb_first,
                "namespace_verb": namespace_verb,
                "first_segment": first_seg,
                "param_count": param_count,
                "enum_params": len(enum_params),
                "default_params": len(default_params),
                "desc_words": words,
                "has_when_marker": any(m in desc.lower() for m in WHEN_MARKERS),
                "has_output_schema": has_output_schema,
                "description": desc,
            }
        )

    rows.sort(key=lambda r: r["name"])
    declared = len(rows)

    verb_first_violations = [r for r in rows if not r["verb_first"] and not r["namespace_verb"]]
    over8 = [r for r in rows if r["param_count"] > 8]
    over5 = [r for r in rows if r["param_count"] > 5]
    short_desc = [r for r in rows if r["desc_words"] < 10]
    no_enum = [r for r in rows if r["param_count"] > 0 and r["enum_params"] == 0]
    no_output_schema = [r for r in rows if not r["has_output_schema"]]

    summary = {
        "declared": declared,
        "verb_first_ratio": round(sum(1 for r in rows if r["verb_first"]) / declared, 3)
        if declared
        else 0.0,
        "verb_style_ratio": round(
            sum(1 for r in rows if r["verb_first"] or r["namespace_verb"]) / declared, 3
        )
        if declared
        else 0.0,
        "param_count_avg": round(sum(r["param_count"] for r in rows) / declared, 2)
        if declared
        else 0.0,
        "param_count_max": max((r["param_count"] for r in rows), default=0),
        "over_5_params": len(over5),
        "over_8_params": len(over8),
        "over_8_param_exemptions": sorted(OVER_8_PARAM_EXEMPTIONS),
        "short_desc_lt10": len(short_desc),
        "no_enum_tools": len(no_enum),
        "enum_params_total": sum(r["enum_params"] for r in rows),
        "default_params_total": sum(r["default_params"] for r in rows),
        "when_marker_ratio": round(sum(1 for r in rows if r["has_when_marker"]) / declared, 3)
        if declared
        else 0.0,
        "output_schema_ratio": round(sum(1 for r in rows if r["has_output_schema"]) / declared, 3)
        if declared
        else 0.0,
        "no_output_schema": len(no_output_schema),
        # T-S-01 / D-工-1 floor: every declared tool must advertise the
        # canonical envelope via ``_with_output_schema``.
        "output_schema_floor_ok": len(no_output_schema) == 0,
    }

    return {
        "declared": declared,
        "summary": summary,
        "violations": {
            "not_verb_first": [r["name"] for r in verb_first_violations],
            "over_8_params": [r["name"] for r in over8],
            "over_5_params": [r["name"] for r in over5],
            "short_description_lt10": [r["name"] for r in short_desc],
            "no_enum_params": [r["name"] for r in no_enum],
            "no_output_schema": [r["name"] for r in no_output_schema],
        },
        "tools": rows,
    }


def main() -> int:
    src = SRC.read_text(encoding="utf-8")
    result = audit_tools(src)
    s = result["summary"]

    print(f"Tool description audit (D-工-1) — {datetime.date.today().isoformat()}")
    print(f"Declared tools: {s['declared']}")
    print(
        f"Verb-first ratio: {s['verb_first_ratio']:.1%} "
        f"(verb-style incl. namespace+verb: {s['verb_style_ratio']:.1%})"
    )
    print(
        f"Param count: avg {s['param_count_avg']} / max {s['param_count_max']} "
        f"(>5: {s['over_5_params']}, >8: {s['over_8_params']})"
    )
    if s["over_8_params"]:
        exemptions = ", ".join(s["over_8_param_exemptions"])
        print(f"  Sanctioned >8-param exemptions (documented): {exemptions}")
    print(
        f"Description: <10 words: {s['short_desc_lt10']}, "
        f"when-marker ratio: {s['when_marker_ratio']:.1%}"
    )
    print(
        f"enum params: {s['enum_params_total']}, "
        f"default params: {s['default_params_total']}, "
        f"tools w/o enum: {s['no_enum_tools']}"
    )
    print(
        f"outputSchema: {s['output_schema_ratio']:.1%} "
        f"({s['no_output_schema']} missing, floor_ok={s['output_schema_floor_ok']})"
    )

    v = result["violations"]
    for label, names in v.items():
        if names:
            print(
                f"\n{label} ({len(names)}): {', '.join(names[:15])}"
                + (" …" if len(names) > 15 else "")
            )

    out_dir = OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"tool-desc-{datetime.date.today().isoformat()}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
