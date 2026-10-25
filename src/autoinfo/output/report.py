"""Report synthesis internals (extracted from output/__init__.py).

``generate_report`` stays in the hub. Two intra-module callees are patched
through the hub by tests, so they are read with function-local hub imports:
``_call_llm_for_report_synthesis`` (41 sites) and ``_llm_json_extract``
(13 sites).
"""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Any, Callable

from autoinfo.config import Config, get_config_path, load_config
from autoinfo.llm import call_with_fallback
from autoinfo.output.audience import _REPORT_AUDIENCE_PROMPTS, _normalize_report_audience
from autoinfo.output.contracts import ReportData
from autoinfo.output.sources import _derive_source_label
from autoinfo.prompts import get_prompt
from autoinfo.quality_constraints import (
    EDITORIAL_OPENING_HEDGE_CONSTRAINT,
    NO_FABRICATION_CONSTRAINT,
    SYNTHESIS_ENTITY_GROUNDING_CONSTRAINT,
    SYNTHESIS_SIGNAL_TRACEABILITY_CONSTRAINT,
    URL_VERBATIM_CONSTRAINT,
)

if TYPE_CHECKING:
    from autoinfo.llm import LLMExtractor

logger = logging.getLogger("autoinfo.output")


def _hub(name: str) -> Any:
    """Read a hub-resident name at call time (tests patch it on autoinfo.output)."""
    import autoinfo.output as hub

    return getattr(hub, name)


_RETRY_MAX_DETAIL_ENTRIES = 12


_RETRY_MAX_ENTRY_SUMMARY_CHARS = 80


_RETRY_DETAIL_CHAR_BUDGET = 4000


_RETRY_MAX_ATTEMPTS = 4


_RETRY_BACKOFF_SECONDS = 60.0


_DEDICATED_PRODUCT_PROMPT_MAX_FINDINGS = 12


_DEDICATED_PRODUCT_PROMPT_MAX_FINDING_CHARS = 200


_DEDICATED_PRODUCT_PROMPT_MAX_SUMMARY_CHARS = 1000


def _build_report_entries_detail(
    entries: list[dict[str, Any]],
    groupings: list[dict[str, Any]],
    max_detail_entries: int = 40,
    max_entry_summary_chars: int = 120,
    detail_char_budget: int | None = None,
    rmb_usd_rate: float | None = None,
) -> str:
    """Build the theme-grouped entry detail block embedded in the synthesis
    prompt.

    Defaults reproduce the original behavior exactly (40 highest-relevance
    entries × 120-char summaries).  *detail_char_budget* caps the block's
    total length; when the cap is hit, remaining entries are dropped and a
    truncation note appended — used by the smaller-prompt retry in
    :func:`_generate_executive_summary` so the prompt stays within the size
    the configured LLM endpoint reliably answers.

    *rmb_usd_rate* (config-driven, issue #203) appends the canonical USD
    equivalent to RMB-denominated amounts in titles/summaries (``None`` reads
    it from config).
    """
    if rmb_usd_rate is None:
        rmb_usd_rate = _hub("_get_rmb_usd_rate")()
    ranked = sorted(
        (e for g in groupings for e in g["entries"]),
        key=lambda e: float(e.get("relevance_score") or 0.0),
        reverse=True,
    )[:max_detail_entries]
    picked_ids = {id(e) for e in ranked}

    detail_lines: list[str] = []
    truncated = False
    for g in groupings:
        if truncated:
            break
        picked = [e for e in g["entries"] if id(e) in picked_ids]
        for e in picked:
            title, summary = _hub("_digest_entry_text")(e, rmb_usd_rate)
            line = f"- [{g['theme']}] {title or '(no title)'}: {summary[:max_entry_summary_chars]}"
            # Issue #279: thread source_url into the synthesis context.
            src = str(e.get("source_url") or "").strip()
            if src:
                line = f"{line} (Source: {src})"
            if detail_char_budget is not None:
                if len("\n".join(detail_lines + [line])) > detail_char_budget:
                    truncated = True
                    break
            detail_lines.append(line)
        if not truncated and len(picked) < len(g["entries"]):
            detail_lines.append(
                f"- [{g['theme']}] (+{len(g['entries']) - len(picked)} more entries in this theme)"
            )
    if truncated:
        detail_lines.append("(further entries omitted for brevity)")
    return "\n".join(detail_lines) or "(no entries)"


def _build_report_synthesis_prompt(
    entries_detail: str,
    custom_instructions: str = "",
    target_audience: str = "",
    domains: list[str] | None = None,
    product_family: str = "report",
) -> str:
    """Assemble the report-synthesis prompt.

    Shared by the primary call and the truncated-prompt retry in
    :func:`_generate_executive_summary` so both request and parse the same
    structure (including the §2.4 product sections for product families).
    """
    cross_domain_prefix = ""
    if domains and len(domains) >= 2:
        cross_domain_prefix = (
            f"You are synthesizing information from {len(domains)} domains: "
            f"{', '.join(domains)}. Present a cohesive view that connects "
            "findings across domains.\n\n"
        )

    prompt = (
        cross_domain_prefix + "Write a report synthesis analyzing the following knowledge base "
        "entries (grouped by theme). Use the actual content: cite specific "
        "findings, studies, and data points from the entries. When a key "
        "finding, recommendation, or trend is backed by a specific entry, "
        "cite its source inline as (Source: URL). Do NOT describe "
        "the report structure or the writing instructions — write the analysis "
        "itself.\n\n"
        f"Themes and entries:\n{entries_detail}\n\n"
        "Return plain Markdown with this exact structure:\n\n"
        "## Executive Summary\n"
        "<2-3 paragraphs>\n\n"
        "## Key Findings\n"
        "- <finding 1>\n"
        "- <finding 2>\n\n"
        "## Recommendations\n"
        "- <recommendation 1>\n"
        "- <recommendation 2>\n\n"
        "Use exactly the heading names above. Do NOT wrap your answer in a "
        "code fence or emit JSON."
    )
    if custom_instructions:
        prompt += f"\n\nAdditional instructions: {custom_instructions}"
    # -- Product-specific synthesis sections (todo 7, spec §2.4) -------------
    product_structure = _hub("_REPORT_PRODUCT_SYNTHESIS_PROMPTS").get(product_family, "")
    if product_structure:
        prompt += f"\n\n{product_structure}"
    # Issue #140: differentiate premium vs enterprise briefing coverage scope
    # so the two paid products read as distinct angles (premium = deep 1-2
    # topics; enterprise = decision-oriented 4-6 topics).
    scope_guidance = _hub("_DIGEST_PRODUCT_SCOPE_GUIDANCE").get(product_family)
    if scope_guidance:
        prompt += f"\n\n{scope_guidance}"
    # Issue #179: hard no-fabrication constraint — the report synthesis must
    # write ONLY from the entries' stated content (no invented teams/motives/
    # numbers/directions or entity descriptions beyond the sources).
    # Canonical string lives in quality_constraints (#194 spec D).
    prompt += f"\n\n{NO_FABRICATION_CONSTRAINT}"
    # Issue #200: never rename/abstract source signals into new terms — a
    # financial report turned "low VIX, inflation shocks, and excessive AI
    # spending" into the novel "low market breadth".  Canonical string lives
    # in quality_constraints (rides digest + report paths identically).
    prompt += f"\n\n{SYNTHESIS_SIGNAL_TRACEABILITY_CONSTRAINT}"
    # Issue #445: every named entity must exist in a supplied entry, and a
    # (Source: URL) must point at the entry the sentence is actually about.
    prompt += f"\n\n{SYNTHESIS_ENTITY_GROUNDING_CONSTRAINT}"
    # Issue #207: every (Source: URL) must be taken VERBATIM from the KB
    # Entries list — never re-slug or invent a URL (mirror of the presentation
    # prompt's #93 wording).  Canonical string lives in quality_constraints.
    prompt += f"\n\n{URL_VERBATIM_CONSTRAINT}"
    # Issue #210: the Executive Summary / Recommendations opener is an
    # editorial voice that invited unhedged market-direction/motive assertions
    # ("the smart money is betting on…").  Hedge discipline pinned (mirrors
    # the magazine editorial_intro constraint from #191).
    prompt += f"\n\n{EDITORIAL_OPENING_HEDGE_CONSTRAINT}"
    # -- Structured audience adaptation -----------------------------------
    audience = _normalize_report_audience(target_audience)
    audience_prompt = _REPORT_AUDIENCE_PROMPTS.get(audience, "")
    if audience_prompt:
        prompt += f"\n\n{audience_prompt}"
    return prompt


def _report_product_fields_for_family(product_family: str) -> tuple[str, ...]:
    """Required §2.4 product fields for a product synthesis family.

    Returns ``()`` for the default ``report`` family and any unknown family
    so the dedicated product-sections prompt never fires outside the product
    template families (backward compatibility).  ``key_metrics`` is
    enterprise-only.
    """
    if product_family not in _hub("_REPORT_PRODUCT_SYNTHESIS_PROMPTS"):
        return ()
    fields: tuple[str, ...] = ("implications", "risks", "action_required")
    if product_family == "enterprise-briefing":
        fields += ("key_metrics",)
    return fields


def _build_product_sections_prompt(
    parsed: dict[str, Any],
    product_family: str,
    max_findings: int = _DEDICATED_PRODUCT_PROMPT_MAX_FINDINGS,
    max_finding_chars: int = _DEDICATED_PRODUCT_PROMPT_MAX_FINDING_CHARS,
    max_summary_chars: int = _DEDICATED_PRODUCT_PROMPT_MAX_SUMMARY_CHARS,
) -> str:
    """Build the small dedicated prompt that asks the model to emit ONLY the
    §2.4 product sections for an already-produced synthesis.

    Carries the produced executive summary and key findings (both bounded so
    the total stays ~2–3.5K chars, far below any prompt-size concern) plus
    the family's section format spec, so the response parses with
    :func:`_parse_report_markdown` (``require_exec_summary=False``).  The
    callers only merge the product fields back, so any model output outside
    the requested sections is ignored.
    """
    summary = (parsed.get("executive_summary") or "").strip()
    if len(summary) > max_summary_chars:
        summary = summary[:max_summary_chars].rstrip() + "..."
    finding_texts = [
        ((f.get("text") if isinstance(f, dict) else f) or "").strip()
        for f in (parsed.get("key_findings") or [])[:max_findings]
    ]
    findings = "\n".join(f"- {t[:max_finding_chars].rstrip()}" for t in finding_texts)
    return (
        "You are a report synthesis assistant. Below are the executive summary "
        "and key findings already produced for a briefing. Emit ONLY the "
        "additional product sections listed below — do NOT repeat the "
        "executive summary, key findings, recommendations, or any other "
        "content.\n\n"
        f"## Executive Summary\n{summary or '(none)'}\n\n"
        f"## Key Findings\n{findings or '(none)'}\n\n"
        + str(_hub("_REPORT_PRODUCT_SYNTHESIS_PROMPTS")[product_family])
    )


def _generate_executive_summary(
    extractor: LLMExtractor,
    entries: list[dict[str, Any]],
    groupings: list[dict[str, Any]],
    custom_instructions: str = "",
    target_audience: str = "",
    domains: list[str] | None = None,
    product_family: str = "report",
    *,
    max_synthesis_attempts: int = _RETRY_MAX_ATTEMPTS,
    retry_backoff_seconds: float = _RETRY_BACKOFF_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Generate the report synthesis (summary + findings + recommendations).

    Asks the LLM for flat Markdown with ``## Executive Summary`` /
    ``## Key Findings`` / ``## Recommendations`` headings — the default
    model emits markdown far more reliably than a nested JSON schema —
    and parses it by heading (see :func:`_parse_report_markdown`).

    For product template families (``premium-briefing`` /
    ``enterprise-briefing`` / ``magazine-digest``) the requested structure
    additionally includes the §2.4 product sections — ``## Implications`` /
    ``## Risks & Opportunities`` / ``## Action Required`` (index-aligned
    with Key Findings), plus ``## Key Metrics`` for enterprise-briefing —
    keyed by the resolved family. The default ``report`` family is
    unchanged (spec §2.4, todo 7).

    Falls back to a legacy single-string JSON summary via the extractor,
    and finally to a bullet-list summary, so the report is never empty.
    When an attempt returns empty (or the parsed result lacks an executive
    summary) — the configured endpoint flaps with genuine empty completions
    for ~40–60-min "bad windows" at ALL prompt sizes — the call is retried
    with a condensed entries-detail prompt (see
    :func:`_build_report_entries_detail`) up to *max_synthesis_attempts*
    times total, sleeping *retry_backoff_seconds* via *sleep_fn* between
    attempts, so one ``generate_report`` can bridge an endpoint bad window
    without an unbounded loop (round-2 F3 fix; both bounds injectable for
    tests).  Attempt 1 uses the full-size prompt; attempts 2+ reuse the
    condensed prompt.

    For product families, when the synthesis succeeds but the parsed result
    lacks required §2.4 product fields (the model often omits the trailing
    sections), a SECOND small dedicated prompt (see
    :func:`_build_product_sections_prompt`) is issued — bounded to at most
    one call — asking for ONLY those sections, and the parsed sections are
    merged into the result.
    Returns a dict ``{"executive_summary": str, "key_findings": list[str],
    "recommendations": list[str]}`` — never raises.
    """
    from autoinfo.output import fault_inject

    try:
        fault_inject.maybe_fault("summary")
    except Exception:
        fallback = _hub("_deterministic_synthesis_fallback")(
            entries, summary_prefix="This report covers"
        )
        return {
            "executive_summary": fallback["executive_summary"],
            "key_findings": fallback["key_findings"],
            "recommendations": fallback["recommendations"],
        }

    entries_detail = _build_report_entries_detail(entries, groupings)
    prompt = _build_report_synthesis_prompt(
        entries_detail,
        custom_instructions=custom_instructions,
        target_audience=target_audience,
        domains=domains,
        product_family=product_family,
    )
    retry_prompt = _build_report_synthesis_prompt(
        _build_report_entries_detail(
            entries,
            groupings,
            max_detail_entries=_RETRY_MAX_DETAIL_ENTRIES,
            max_entry_summary_chars=_RETRY_MAX_ENTRY_SUMMARY_CHARS,
            detail_char_budget=_RETRY_DETAIL_CHAR_BUDGET,
        ),
        custom_instructions=custom_instructions,
        target_audience=target_audience,
        domains=domains,
        product_family=product_family,
    )
    retry_prompt_usable = len(retry_prompt) < len(prompt)

    # Primary path: flat markdown synthesis (reliable with the default model),
    # with a bounded multi-attempt retry loop against endpoint bad windows.
    parsed: dict[str, Any] = {}
    for attempt in range(1, max_synthesis_attempts + 1):
        if attempt > 1:
            if not retry_prompt_usable:
                break
            logger.info(
                "Report synthesis attempt %d/%d returned no executive summary; "
                "sleeping %.0fs then retrying with condensed prompt "
                "(%d -> %d chars)",
                attempt - 1,
                max_synthesis_attempts,
                retry_backoff_seconds,
                len(prompt),
                len(retry_prompt),
            )
            sleep_fn(retry_backoff_seconds)
        attempt_prompt = prompt if attempt == 1 else retry_prompt
        parsed = _parse_report_markdown(_hub("_call_llm_for_report_synthesis")(attempt_prompt))
        if parsed.get("executive_summary"):
            break

    if parsed.get("executive_summary"):
        # Round-2 F3 fix: the model often omits the trailing §2.4 product
        # sections even when the synthesis succeeds.  For product families,
        # when any required section is missing/empty, issue ONE small
        # dedicated prompt (decoupled from the base synthesis call) and
        # merge the parsed sections back.
        product_fields = _report_product_fields_for_family(product_family)
        if product_fields and any(not parsed.get(f) for f in product_fields):
            sections_prompt = _build_product_sections_prompt(parsed, product_family)
            logger.info(
                "Report synthesis succeeded but product sections (%s) missing; "
                "issuing dedicated small prompt (%d chars)",
                ", ".join(f for f in product_fields if not parsed.get(f)),
                len(sections_prompt),
            )
            sections_parsed = _parse_report_markdown(
                _hub("_call_llm_for_report_synthesis")(sections_prompt),
                require_exec_summary=False,
            )
            for field in product_fields:
                if sections_parsed.get(field):
                    parsed[field] = sections_parsed[field]
        return parsed

    # Legacy path: single-string JSON summary via the extractor.
    try:
        raw = _hub("_llm_json_extract")(extractor, prompt, "executive_summary")
        if raw and isinstance(raw, str) and raw.strip():
            return {
                "executive_summary": raw.strip(),
                "key_findings": [],
                "recommendations": [],
            }
    except Exception as exc:
        logger.warning("Executive summary via LLM failed: %s", exc)

    # Fallback
    # Issue #217: the fallback must still carry non-empty D1-required
    # sections — key_findings / recommendations derived from the real
    # entries (never fabricated), so D1 never blocks the report.
    # Issue #338: the previous per-theme count summary ("This report covers
    # N entries grouped into M themes: - **API**: N entry(ies)") leaked the
    # internal grouping/search mechanics to end users — use the user-facing
    # summary derived from the real entry titles instead.
    fallback = _hub("_deterministic_synthesis_fallback")(
        entries, summary_prefix="This report covers"
    )
    return {
        "executive_summary": fallback["executive_summary"],
        "key_findings": fallback["key_findings"],
        "recommendations": fallback["recommendations"],
    }


def _call_llm_for_report_synthesis(prompt: str) -> str:
    """Call the configured LLM to synthesize report Markdown.

    Uses the shared :func:`call_with_fallback` helper in plain-text mode
    (no JSON mode) — the default model emits the flat ``## Executive
    Summary`` / ``## Key Findings`` / ``## Recommendations`` structure
    reliably while a nested JSON schema frequently comes back empty.
    Returns the raw Markdown text (possibly empty) on success, ``""`` on
    failure.
    """
    from autoinfo.output import fault_inject

    try:
        fault_inject.maybe_fault("report")
    except Exception as exc:
        logger.warning("FAULT_INJECT[report]: %s", exc)
        return ""

    config_path = get_config_path()
    if config_path and config_path.is_file():
        try:
            config = load_config(config_path)
        except Exception:
            config = Config()
    else:
        config = Config()

    model = config.llm.resolve_model()
    try:
        response = call_with_fallback(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": get_prompt("report_synthesis_system"),
                },
                {"role": "user", "content": prompt},
            ],
            json_mode=False,
            max_tokens=8000,
            temperature=0.1,
            api_key=config.llm.api_key or None,
            base_url=config.llm.base_url or None,
        )
    except Exception as exc:
        logger.warning("Report synthesis via LLM failed: %s", exc)
        return ""
    content: str = response.choices[0].message.content or ""
    return content.strip()


_GLUED_BULLET_SEP = re.compile(r"(?<=\))- ?")


def _split_glued_bullets(text: str) -> list[str]:
    """Split a bullet body that carries glue-glued follow-on bullets (issue #14).

    The LLM sometimes returns Key Findings bullets joined inline without
    newlines — ``- a (Source: u)- b (Source: u)- c`` — so the whole run is
    seen by ``is_bullet`` as ONE item.  A ``)`` immediately before a ``-`` is
    the glue boundary (a ``(Source: URL)`` citation suffix followed by the
    next bullet marker), and each split part preserves its own ``(Source: u)``
    suffix.  Legitimate prose where ``)`` is *not* followed by ``-`` is never
    split.
    """
    return [part for part in _GLUED_BULLET_SEP.split(text) if part]


def _parse_report_markdown(content: str, require_exec_summary: bool = True) -> dict[str, Any]:
    """Parse a Markdown report synthesis into the report context schema.

    Handles the structure requested by the report-synthesis prompt:
    ``## Executive Summary`` (paragraphs), ``## Key Findings`` (bullets)
    and ``## Recommendations`` (bullets).  For product template families
    (spec §2.4, todo 7) it also parses ``## Implications`` (bullets →
    ``list[str]``), ``## Risks & Opportunities`` (``|``-delimited bullets →
    ``list[dict]`` ``{title, likelihood, impact, mitigation}``),
    ``## Action Required`` (bullets → ``list[str]``) and ``## Key Metrics``
    (``|``-delimited bullets → ``list[dict]`` ``{metric, value, source}``).
    Returns ``{}`` when *content* is empty, or when *content* carries no
    executive summary and *require_exec_summary* is set (default).  The
    dedicated product-sections response (which intentionally omits the
    executive summary) is parsed with ``require_exec_summary=False``.
    """
    if not content:
        return {}
    result: dict[str, Any] = {
        "executive_summary": "",
        "key_findings": [],
        "recommendations": [],
        "implications": [],
        "risks": [],
        "action_required": [],
        "key_metrics": [],
    }
    current_section = ""
    summary_lines: list[str] = []

    def is_bullet(text: str) -> bool:
        return bool(re.match(r"^(?:[-*]|\d+[.)])\s+\S", text))

    def bullet_text(text: str) -> str:
        return re.sub(r"^(?:[-*]|\d+[.)])\s+", "", text).strip()

    for raw in content.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped.lstrip("#").strip().lower()
            continue
        if not current_section:
            continue
        if current_section in ("executive summary", "summary", "overview"):
            if stripped and not line.startswith(("---", "***")):
                summary_lines.append(stripped)
        elif current_section in ("key findings", "findings", "main findings"):
            if is_bullet(stripped):
                for item in _split_glued_bullets(bullet_text(stripped)):
                    item = item.strip()
                    if item:
                        result["key_findings"].append(item)
        elif current_section in ("recommendations", "next steps", "action items"):
            if is_bullet(stripped):
                item = bullet_text(stripped)
                if item:
                    result["recommendations"].append(item)
        elif current_section == "implications":
            if is_bullet(stripped):
                item = bullet_text(stripped)
                if item:
                    result["implications"].append(item)
        elif current_section in ("risks & opportunities", "risks", "risk matrix"):
            if is_bullet(stripped):
                parts = [p.strip() for p in bullet_text(stripped).split("|")]
                if len(parts) >= 4 and parts[0]:
                    result["risks"].append(
                        {
                            "title": parts[0],
                            "likelihood": parts[1],
                            "impact": parts[2],
                            "mitigation": " | ".join(parts[3:]),
                        }
                    )
        elif current_section in ("action required", "actions"):
            if is_bullet(stripped):
                item = bullet_text(stripped)
                if item:
                    result["action_required"].append(item)
        elif current_section in ("key metrics", "metrics"):
            if is_bullet(stripped):
                parts = [p.strip() for p in bullet_text(stripped).split("|")]
                if len(parts) >= 3 and parts[0]:
                    result["key_metrics"].append(
                        {
                            "metric": parts[0],
                            "value": parts[1],
                            "source": " | ".join(parts[2:]),
                        }
                    )

    result["executive_summary"] = "\n\n".join(summary_lines).strip()
    if require_exec_summary and not result["executive_summary"]:
        return {}
    return result


def _llm_json_extract(
    extractor: LLMExtractor,
    prompt: str,
    key: str,
) -> Any:
    """Call the LLM and extract a top-level JSON field.

    Uses :class:`LLMExtractor` under the hood by wrapping the prompt in
    a minimal ``Item``.  Returns the value of *key* from the parsed
    JSON response, or ``None`` on failure.

    Free-provider resilience: the extraction path returns an EMPTY result
    (not an exception) on transient parse failure; retry once before
    giving up, mirroring the two-attempt pattern of ``_report_llm_call``.
    """
    from autoinfo.models import Item  # noqa: PLC0415

    dummy = Item(
        id="_report_llm_call",
        source_name="report",
        source_type="internal",
        source_url="",
        title=key.replace("_", " ").title(),
        content=prompt,
    )
    result = extractor.extract(dummy, schema=[key])
    value = result.custom_fields.get(key) if result else None
    if value is None:
        result = extractor.extract(dummy, schema=[key])
        value = result.custom_fields.get(key) if result else None
    return value


def _report_data_to_dict(report_data: ReportData, source_tier_badge: bool = True) -> dict[str, Any]:
    """Convert a :class:`ReportData` instance to a flat dict for Jinja2 rendering.

    Maps ``ReportSection.items`` → ``entries`` to match the variable
    names expected by the report templates (``report.md.j2``,
    ``report.html.j2``).  Also surfaces the §2.1 product fields
    (``implications`` / ``risks`` / ``action_required`` / ``key_metrics``,
    spec §2.4, todo 7) — empty lists for plain reports, so existing callers
    are unchanged.

    Issue #342: the report-path magazine product (``generate_report`` with
    the ``magazine-digest`` template) reads the top-level ``entries`` list
    for its per-title clusters.  Build it from the references — the report
    path already derives the specific source labels there — so the magazine
    layout renders real per-title clusters instead of the
    ``_No articles found..._`` empty-state.
    """
    # #325: stamp a derived ``source_label`` on every reference so the
    # report-path templates (report/column/premium-briefing/enterprise-briefing
    # /magazine-digest) can render ``ref.source_label or ref.source_platform``
    # and never show the generic "(RSS)" for stale pre-#323 entries.  A
    # reference may already carry the derived label (the generate_report
    # references builder calls _derive_source_label); when it does not (e.g.
    # a flat context built directly), derive it here from the ref's own data.
    labeled_refs = []
    for ref in report_data.references:
        ref_label = str(ref.get("source_label") or "").strip()
        if not ref_label:
            ref_label = _derive_source_label(ref, str(ref.get("domain") or report_data.domain))
        labeled_refs.append({**ref, "source_label": ref_label})

    entries = [
        {
            "title": ref.get("title", ""),
            "summary": "",
            "source_url": ref.get("source_url", ""),
            "source_type": ref.get("source_type", ""),
            "source_platform": ref.get("source_label", "") or ref.get("source_platform", ""),
            "source_label": ref.get("source_label", ""),
            "relevance_score": None,
            "collected_at": "",
        }
        for ref in labeled_refs
    ]
    sections = [
        {
            "title": s.title,
            "content": s.content,
            "entries": [
                {
                    **item,
                    "source_platform": (
                        item.get("source_label", "") or item.get("source_platform", "")
                    ),
                }
                for item in s.items
            ],
        }
        for s in report_data.sections
    ]
    if report_data.grouping_degradation_marker:
        # #120 (C4): the honest "grouped by source" marker leads the section
        # list when grouping degraded (mirrors the digest normalization path).
        sections.insert(0, {"marker": report_data.grouping_degradation_marker})
    return {
        "title": report_data.title,
        "generated_at": report_data.generated_at,
        "domain": report_data.domain,
        "collection_id": report_data.collection_id,
        # #445: the report synthesis cites its sources inline, so the same
        # citation-grounding backstop the digest path applies runs here.
        "executive_summary": _hub("_ground_synthesis_citations")(
            report_data.executive_summary, entries
        ),
        "key_findings": report_data.key_findings,
        "recommendations": report_data.recommendations,
        "implications": report_data.implications,
        "risks": report_data.risks,
        "action_required": report_data.action_required,
        "key_metrics": report_data.key_metrics,
        "source_tier_badge": source_tier_badge,
        "entries": entries,
        "sections": sections,
        "references": labeled_refs,
        "appendices": report_data.appendices,
        "grouping_degradation_marker": report_data.grouping_degradation_marker,
    }
