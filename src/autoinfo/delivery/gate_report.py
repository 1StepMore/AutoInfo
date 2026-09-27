"""Delivery-layer gate checks + per-product gate reports (shared, todo 13).

This module holds the D1-D3 + authenticity delivery-gate implementation and
the per-product gate-report rendering that was originally written for the
validation delivery packager (``scripts/validation_delivery.py``, concierge
wave task 7). Todo 13 extracted it verbatim into ``src/autoinfo`` so the
Concierge MVP CLI (``autoinfo mvp init``) and the validation packager share
the SAME gate + gate-report code — one implementation, two consumers:

- ``scripts/validation_delivery.py`` carries its own gate/gate-report
  implementation (the importlib-based tests exercise
  ``vd.check_authenticity`` / ``vd.run_delivery_gates`` /
  ``vd._qa_product_key``) and uses :func:`run_delivery_gates` +
  :func:`_build_qa_gate_report` in its bulk ``01-QA-GATES`` section writer.
  The D1 section parser is NOT re-exported from this module: all three sites
  import it from ``autoinfo.section_parser``, the single source of truth
  (issue #400 — the earlier "re-exports these names" claim was false, which is
  exactly how the #396 alias fix silently missed the third copy).
- ``autoinfo.cli.mvp`` uses :func:`write_gate_report` to record the honest
  delivery-layer determinations for a pilot's first product.

Honesty contract (unchanged from task 7): G0-G5 run at PROCESS time
(``autoinfo.quality``); these functions record ONLY the delivery-layer
determinations (D1-D3 delivery gates + authenticity pre-check +
deliver/reject decisions) that were actually made. No G0-G5 data is
recomputed or persisted here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from autoinfo.quality import run_delivery_gates as _quality_run_delivery_gates

# Section parser — single source of truth, re-exported (#400). The ``X as X``
# idiom keeps each name a module attribute so callers, tests and static
# analysis all resolve the SAME object as ``autoinfo.output`` and
# ``scripts/validation_delivery.py``; no local copy may remain.
from autoinfo.section_parser import (
    _D1_NON_REQUIRED_MARKER as _D1_NON_REQUIRED_MARKER,
)
from autoinfo.section_parser import (
    _EMPTY_PLACEHOLDER_RE as _EMPTY_PLACEHOLDER_RE,
)
from autoinfo.section_parser import (
    _ENTRY_HEADING_RE as _ENTRY_HEADING_RE,
)
from autoinfo.section_parser import (
    _LLM_SKELETON_RE as _LLM_SKELETON_RE,
)
from autoinfo.section_parser import (
    _PRODUCT_TYPE_REQUIRED_SECTIONS as _PRODUCT_TYPE_REQUIRED_SECTIONS,
)
from autoinfo.section_parser import (
    _SECTION_HEADING_ALIASES as _SECTION_HEADING_ALIASES,
)
from autoinfo.section_parser import (
    _SLIDE_HEADING_RE as _SLIDE_HEADING_RE,
)
from autoinfo.section_parser import (
    _apply_format_sections as _apply_format_sections,
)
from autoinfo.section_parser import (
    _is_empty_placeholder as _is_empty_placeholder,
)
from autoinfo.section_parser import (
    _sections_from_headings as _sections_from_headings,
)

# Text formats whose content can be structurally inspected as a product.
_INSPECTABLE_FORMATS: dict[str, str] = {
    ".md": "markdown",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".jsonl": "json",
}

# Keys that mark a JSON dict as a structured source entry.
_ENTRY_KEYS = frozenset(
    {"source_url", "source_type", "source_platform", "title", "entry_id", "uuid"}
)

# The D1 heading aliases, the slide/entry/placeholder regexes and the
# per-product-type required-section table all live in
# ``autoinfo.section_parser`` and are re-exported at module top (issue #400).

# Filename keywords -> product type (checked in order).
_PRODUCT_TYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("enterprise-briefing", "enterprise_briefing"),
    ("premium-briefing", "premium_briefing"),
    ("magazine-digest", "magazine_digest"),
    ("presentation", "presentation"),
    ("tutorial", "tutorial"),
    ("magazine", "magazine"),
    ("digest", "digest"),
    ("column", "column"),
)

# Column-template headings (column.md.j2). generate_report persists every
# report (including report_type="column") under the "report" product name, so
# classify by content when the filename alone says report (#172).
_COLUMN_HEADINGS = frozenset(
    {
        "the big idea",
        "deep dive",
        "reader takeaways",
        "implications & outlook",
        "what changed this week",
    }
)

# Canonical D1 sections -> JSON top-level / llm_synthesis key aliases.
_SECTION_SOURCE_KEYS: dict[str, tuple[str, ...]] = {
    "key_findings": ("key_findings", "key-findings", "findings"),
    "summary": ("summary", "executive_summary", "executive-summary"),
    "recommendations": ("recommendations", "next_steps", "conclusion"),
}

# JSON filenames that carry run/coverage metadata rather than a report product.
_METADATA_JSON_NAMES = frozenset({"scenarios.json", "manifest.json"})
_METADATA_JSON_PREFIXES = ("coverage-",)
_METADATA_JSON_SUFFIXES = ("_runs.json",)

# Keys that mark a JSON dict as a genuine report product (D1-inspectable).
_REPORT_JSON_MARKERS = frozenset(
    {"title", "entries", "llm_synthesis", "digest_type", "@type", "sections"}
)


def _is_metadata_json(file_path: Path, parsed: Any) -> bool:
    """True when *file_path* is JSON that is NOT a report product (#169).

    Metadata JSONs (``scenarios.json``, ``coverage-*.json``, ``*_runs.json``,
    ``manifest.json``) carry run/coverage state rather than a rendered
    product; they must run with ``product_type="RAW"`` so the D1-D3 gates
    trivially skip. A parsed dict exposing report markers
    (``title``/``entries``/``llm_synthesis``/...) is a real product
    regardless of its filename.
    """
    name = file_path.name.lower()
    if name in _METADATA_JSON_NAMES:
        return True
    if name.startswith(_METADATA_JSON_PREFIXES) or name.endswith(_METADATA_JSON_SUFFIXES):
        return True
    if isinstance(parsed, dict):
        return not bool(_REPORT_JSON_MARKERS & parsed.keys())
    return False


def _parse_json_payload(file_path: Path) -> Any:
    """Load JSON / JSONL content; returns ``None`` when unparseable."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — binary or unreadable file
        return None
    if file_path.suffix.lower() == ".jsonl":
        objs: list[Any] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                objs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return objs or None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _parse_frontmatter(file_path: Path) -> dict[str, Any]:
    """Extract YAML frontmatter (``---``-delimited) from a markdown file."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        import yaml

        data = yaml.safe_load(text[3:end])
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def _json_entries(parsed: Any) -> list[dict[str, Any]]:
    """Extract structured source-entry dicts from a parsed JSON payload."""
    if isinstance(parsed, list):
        return [e for e in parsed if isinstance(e, dict) and (_ENTRY_KEYS & e.keys())]
    if not isinstance(parsed, dict):
        return []
    for key in ("entries", "items", "results", "articles", "payload"):
        val = parsed.get(key)
        if isinstance(val, list):
            hit = [e for e in val if isinstance(e, dict) and (_ENTRY_KEYS & e.keys())]
            if hit:
                return hit
    if _ENTRY_KEYS & parsed.keys():
        return [parsed]
    return []


def _detect_product_type(file_path: Path, body: str = "") -> str:
    """Infer the product type from the artifact path (#172).

    Filename keywords win (presentation/digest/tutorial/column/magazine/
    enterprise-briefing/premium-briefing/magazine-digest); everything else
    defaults to ``report``. Column products are persisted
    under the ``report`` name (generate_report persists report_type="column"
    as report-markdown-*), so column-template headings in the body upgrade a
    report-named file to ``column``.
    """
    rel = file_path.as_posix().lower()
    for keyword, ptype in _PRODUCT_TYPE_KEYWORDS:
        if keyword in rel:
            return ptype
    if body and any(
        line.strip().lstrip("#").strip().lower() in _COLUMN_HEADINGS for line in body.splitlines()
    ):
        return "column"
    return "report"


def _section_value(parsed: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    """First non-empty value for *aliases* at top level or in llm_synthesis."""
    llm_synthesis = parsed.get("llm_synthesis")
    llm_synthesis = llm_synthesis if isinstance(llm_synthesis, dict) else {}
    for scope in (parsed, llm_synthesis):
        for key in aliases:
            val = scope.get(key)
            if val not in (None, "", [], {}):
                return val
    return None


def _build_product_output(file_path: Path, bucket: str) -> dict[str, Any]:
    """Adapt an artifact file into the ``product_output`` dict quality.py expects.

    RAW/KB content and non-inspectable binary formats run with
    ``product_type="RAW"`` so the D gates trivially skip (that content was
    already gated at pipeline time). PROCESSED text products (md/html/json)
    get the real D1-D3 treatment with sections derived from headings/keys.
    """
    suffix = file_path.suffix.lower()
    fmt = _INSPECTABLE_FORMATS.get(suffix)
    product_type = "RAW" if (bucket in ("RAW", "KB") or fmt is None) else "PROCESSED"
    entries: list[dict[str, Any]] = []
    sections: dict[str, Any] = {}
    body: Any = ""
    parsed: Any = None
    if fmt in ("markdown", "html"):
        try:
            body = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        format_type = _detect_product_type(file_path, str(body))
        if product_type != "RAW":
            # Carry the inferred product (presentation/report/column/...) so
            # the D1 gate can apply product-appropriate completeness rules
            # (issue #217 follow-up: presentation decks are slide content,
            # not key_findings/summary/recommendations).
            product_type = format_type
        sections = _apply_format_sections(
            _sections_from_headings(str(body), format_type), format_type
        )
    elif fmt == "json":
        try:
            body = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            body = ""
        parsed = _parse_json_payload(file_path)
        # Metadata JSONs (scenarios.json / coverage-* / *_runs.json /
        # manifest.json, or any dict without report markers) are run/coverage
        # bookkeeping, not report products — treat as RAW so the D gates skip
        # instead of rejecting them on empty report sections (#169).
        if _is_metadata_json(file_path, parsed):
            product_type = "RAW"
        else:
            entries = _json_entries(parsed)
            if isinstance(parsed, dict):
                sections = {
                    "key_findings": _section_value(parsed, _SECTION_SOURCE_KEYS["key_findings"]),
                    "summary": _section_value(parsed, _SECTION_SOURCE_KEYS["summary"]),
                    "recommendations": _section_value(
                        parsed, _SECTION_SOURCE_KEYS["recommendations"]
                    ),
                }
    key_findings = sections.get("key_findings")
    summary = sections.get("summary")
    recommendations = sections.get("recommendations")
    out: dict[str, Any] = {
        "product_type": product_type,
        "format": fmt or "markdown",
        "body": body,
        "key_findings": key_findings if key_findings not in (None, "") else [],
        "summary": summary if summary not in (None, []) else "",
        "recommendations": recommendations if recommendations not in (None, "") else [],
        "entries": entries,
    }
    # Agent JSON-LD payloads (@type: KnowledgeDigest/KnowledgeReport/
    # KnowledgePresentation/...) carry their contract marker here so the
    # D1 gate applies the agent-native completeness check instead of the
    # markdown sections check (issue #217).
    if isinstance(parsed, dict) and "@type" in parsed:
        out["@type"] = parsed["@type"]
    return out


def check_authenticity(file_path: Path) -> dict[str, Any]:
    """Per-artifact authenticity pre-check (field presence only — Oracle R3).

    md/html content files are text products, not structured source entries:
    they pass as N/A (informational frontmatter fields are reported when
    present but never fail). JSON/JSONL payloads are checked for complete
    source provenance — every embedded entry must carry non-empty
    ``source_url`` (not an ``example.com`` placeholder), ``source_type`` and
    ``source_platform``. Payloads without structured entries have nothing to
    verify and pass.

    Returns ``{"authenticity": "pass"|"fail", "reason": str}``.
    """
    suffix = file_path.suffix.lower()
    if suffix in (".md", ".html", ".htm"):
        fm = _parse_frontmatter(file_path)
        reason = "N/A: text content file — not a structured source entry"
        if fm:
            reason += f" (frontmatter fields: {', '.join(sorted(fm)[:6])})"
        return {"authenticity": "pass", "reason": reason}
    parsed = _parse_json_payload(file_path)
    entries = _json_entries(parsed)
    if not entries:
        return {
            "authenticity": "pass",
            "reason": "no structured source entries found in payload — nothing to verify",
        }
    problems: list[str] = []
    is_agent_ld = bool(parsed.get("@type")) if isinstance(parsed, dict) else False
    if is_agent_ld and parsed.get("@type") == "KnowledgePresentation":
        # Slides are content, not source entries; the deck's provenance
        # lives in the top-level "sources" list (issue #217).
        sources = parsed.get("sources") or []
        for i, src in enumerate(sources):
            if not isinstance(src, dict):
                continue
            url = src.get("source_url", "")
            if not isinstance(url, str) or not url.strip():
                problems.append(f"sources[{i}] missing source_url")
        if not sources:
            return {
                "authenticity": "pass",
                "reason": "presentation has no provenance sources — nothing to verify",
            }
    elif is_agent_ld and parsed.get("@type") == "KnowledgeTutorial":
        # Tutorial content (steps/exercises) is authored material; its
        # provenance lives in the top-level "source_entries" list
        # (issue #217).
        source_entries = parsed.get("source_entries") or []
        for i, src in enumerate(source_entries):
            if not isinstance(src, dict):
                continue
            url = src.get("source_url", "")
            if not isinstance(url, str) or not url.strip():
                problems.append(f"source_entries[{i}] missing source_url")
            plat = src.get("source_platform", "")
            if not isinstance(plat, str) or not plat.strip():
                problems.append(f"source_entries[{i}] missing source_platform")
        if not source_entries:
            return {
                "authenticity": "pass",
                "reason": "tutorial has no provenance source_entries — nothing to verify",
            }
    else:
        for i, entry in enumerate(entries):
            url = entry.get("source_url", "")
            if not isinstance(url, str) or not url.strip():
                problems.append(f"entry[{i}] missing source_url")
            elif "example.com" in url:
                problems.append(f"entry[{i}] placeholder source_url: {url}")
            # source_type is required for raw collection payloads but is not
            # part of agent JSON-LD entries (KnowledgeDigest etc. carry
            # source_platform instead) — only require source_platform there
            # (issue #217).
            if is_agent_ld:
                val = entry.get("source_platform", "")
                if not isinstance(val, str) or not val.strip():
                    problems.append(f"entry[{i}] missing source_platform")
            else:
                for field in ("source_type", "source_platform"):
                    val = entry.get(field, "")
                    if not isinstance(val, str) or not val.strip():
                        problems.append(f"entry[{i}] missing {field}")
    if problems:
        shown = "; ".join(problems[:6])
        if len(problems) > 6:
            shown += " ..."
        return {"authenticity": "fail", "reason": shown}
    n = len(entries)
    return {
        "authenticity": "pass",
        "reason": f"{n} structured entr{'y' if n == 1 else 'ies'} with complete source fields",
    }


def _serialize_gate_result(result: Any) -> dict[str, Any]:
    """Turn a quality.QualityResult into a JSON-serializable dict."""
    if result is None:
        return {
            "gate": "unknown",
            "passed": True,
            "score": 0.0,
            "flagged": False,
            "details": {"skipped": True, "reason": "gate did not run"},
        }
    return {
        "gate": getattr(result, "gate_name", ""),
        "passed": bool(getattr(result, "passed", True)),
        "score": float(getattr(result, "score", 0.0) or 0.0),
        "flagged": bool(getattr(result, "flagged", False)),
        "details": dict(getattr(result, "details", {}) or {}),
    }


def run_delivery_gates(file_path: Path, bucket: str) -> dict[str, Any]:
    """Run D1-D3 delivery gates + authenticity pre-check for one artifact.

    Reuses :func:`autoinfo.quality.run_delivery_gates` unmodified — the file
    is adapted into the ``product_output`` dict it expects. Returns
    ``{"gates": {"D1": ..., "D2": ..., "D3": ..., "authenticity": ...},
    "quality": "PASS"|"FAIL"}``; ``quality`` is PASS only when every gate
    passes.
    """
    authenticity = check_authenticity(file_path)
    product_output = _build_product_output(file_path, bucket)
    quality_results = _quality_run_delivery_gates(product_output, {})
    gates = {
        "D1": _serialize_gate_result(quality_results.get("D1-ProductCompleteness")),
        "D2": _serialize_gate_result(quality_results.get("D2-FormatIntegrity")),
        "D3": _serialize_gate_result(quality_results.get("D3-Freshness")),
        "authenticity": authenticity,
    }
    all_pass = (
        gates["D1"]["passed"]
        and gates["D2"]["passed"]
        and gates["D3"]["passed"]
        and gates["authenticity"]["authenticity"] == "pass"
    )
    return {"gates": gates, "quality": "PASS" if all_pass else "FAIL"}


def _failure_reason(gates: dict[str, Any]) -> str:
    """Human-readable summary of why an artifact failed the gates."""
    reasons: list[str] = []
    for name in ("D1", "D2", "D3"):
        g = gates.get(name) or {}
        if not g.get("passed", True):
            details = g.get("details") or {}
            why = details.get("error") or details.get("reason") or f"gate {name} failed"
            reasons.append(f"{name}: {why}")
    auth = gates.get("authenticity") or {}
    if auth.get("authenticity") != "pass":
        reasons.append(f"authenticity: {auth.get('reason', 'failed')}")
    return "; ".join(reasons) or "quality gate failure"


# ---------------------------------------------------------------------------
# Per-product gate reports (concierge wave, plan task 7; shared todo 13)
# ---------------------------------------------------------------------------

_QA_GATES_DIR_NAME = "01-QA-GATES"
# Honesty note carried verbatim in every gate report: the G0-G5 gates run at
# PROCESS time (autoinfo.quality run_quality_gates / LLM extraction), not at
# packaging time. These reports record only the delivery-layer determinations
# (D1-D3 + authenticity + packager-level results) that the caller actually
# made.
_QA_LAYER_NOTE = (
    "G0-G5 于 process 层执行, 本报告记录 delivery 层判定 "
    "(G0-G5 run at process time; this report records the delivery layer's "
    "determinations only: D1-D3 delivery gates + authenticity pre-check + "
    "packager-level deliver/reject decisions). No G0-G5 data is recomputed "
    "or persisted here."
)


def _qa_product_key(path: Path, used: set[str]) -> str:
    """Deterministic, filesystem-safe, collision-free report key for a file.

    ``outputs/medical-research/digest-markdown-20260904.md`` -> ``digest``,
    nested paths keep their directory segments joined with ``__``. A second
    file mapping to the same key gets ``-2``, ``-3``, ... suffixes.
    """
    parts = path.with_suffix("").parts
    key = re.sub(r"[^A-Za-z0-9._-]", "_", "__".join(parts)) or "artifact"
    base = key
    n = 2
    while key in used:
        key = f"{base}-{n}"
        n += 1
    used.add(key)
    return key


def _qa_gate_row(gates: dict[str, Any]) -> list[dict[str, Any]]:
    """The honest gates array for one artifact (D1-D3 + authenticity)."""
    return [
        {
            "gate": name,
            "passed": bool((gates.get(name) or {}).get("passed", True)),
            "details": (gates.get(name) or {}).get("details") or {},
        }
        for name in ("D1", "D2", "D3")
    ] + [
        {
            "gate": "authenticity",
            "passed": (gates.get("authenticity") or {}).get("authenticity") == "pass",
            "details": (gates.get("authenticity") or {}).get("reason", ""),
        }
    ]


def _build_qa_gate_report(
    product_key: str,
    *,
    product: str,
    kind: str,
    delivered: bool,
    quality: str,
    gates: dict[str, Any],
    rejected_reason: str = "",
) -> tuple[str, str]:
    """Render one product's gate report as ``(markdown, json_text)``.

    Records ONLY what the packager actually determined (D1-D3 + authenticity
    + deliver/reject), with the process-layer honesty note — never fabricated
    G0-G5 data.
    """
    payload: dict[str, Any] = {
        "product": product,
        "product_key": product_key,
        "kind": kind,
        "delivered": delivered,
        "rejected_reason": rejected_reason,
        "quality": quality,
        "layer_note": _QA_LAYER_NOTE,
        "gates": _qa_gate_row(gates),
    }
    json_text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    md: list[str] = [
        f"# Gate Report — {product}",
        "",
        f"- Delivered: {'yes' if delivered else 'no (rejected)'}",
        f"- Quality: {quality}",
        f"- Kind: {kind}",
    ]
    if rejected_reason:
        md.append(f"- Rejection reason: {rejected_reason}")
    md.extend(
        [
            "",
            "## Gates",
            "",
            "| Gate | Passed | Details |",
            "|------|--------|---------|",
        ]
    )
    for row in payload["gates"]:
        details = row["details"]
        if isinstance(details, dict):
            details = (
                details.get("error")
                or details.get("reason")
                or json.dumps(details, ensure_ascii=False, default=str)
            )
        md.append(f"| {row['gate']} | {'PASS' if row['passed'] else 'FAIL'} | {details} |")
    md.extend(
        [
            "",
            "## Scope Note",
            "",
            _QA_LAYER_NOTE,
            "",
        ]
    )
    return "\n".join(md), json_text


def write_gate_report(
    out_dir: Path,
    product_file: Path,
    *,
    kind: str = "PROCESSED",
    bucket: str = "PROCESSED",
) -> dict[str, Any]:
    """Gate-check one product file and write its gate report into *out_dir*.

    Shared single-product entry point (concierge wave todo 13): the
    Concierge MVP CLI uses it to record the D1-D3 + authenticity
    determinations for a pilot's first product, next to the product file.
    The validation packager's bulk writer (``_write_qa_gates_section`` in
    ``scripts/validation_delivery.py``) loops over the same building blocks
    (:func:`run_delivery_gates` + :func:`_build_qa_gate_report`).

    ``delivered`` is honest: ``True`` only when every delivery gate passes;
    a failed product keeps its file but the report records
    ``delivered=false`` plus the failure reason.

    Returns ``{quality, delivered, gates, key, md, json}``.
    """
    gates_result = run_delivery_gates(product_file, bucket)
    used: set[str] = set()
    key = _qa_product_key(product_file, used)
    delivered = gates_result["quality"] == "PASS"
    md_text, json_text = _build_qa_gate_report(
        key,
        product=product_file.name,
        kind=kind,
        delivered=delivered,
        quality=gates_result["quality"],
        gates=gates_result["gates"],
        rejected_reason="" if delivered else _failure_reason(gates_result["gates"]),
    )
    md_path = out_dir / f"gate-report-{key}.md"
    json_path = out_dir / f"gate-report-{key}.json"
    md_path.write_text(md_text, encoding="utf-8")
    json_path.write_text(json_text, encoding="utf-8")
    return {
        "quality": gates_result["quality"],
        "delivered": delivered,
        "gates": gates_result["gates"],
        "key": key,
        "md": md_path,
        "json": json_path,
    }
