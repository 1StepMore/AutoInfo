"""Extracted from :mod:`autoinfo.output` (#582 phase 1).

Hub-level helpers are imported inside each function at call time so
``autoinfo.output.<name>`` monkeypatch seams keep working after the move.
"""

from __future__ import annotations

import html
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from autoinfo.output import ReportData

logger = logging.getLogger(__name__)


def _render_report_json(report_data: ReportData, period: str = "weekly") -> str:
    """Render the report data as a JSON string.

    The JSON structure includes ``title``, ``summary``, a flat ``entries``
    list (with ``title``, ``summary``, ``url``, ``date`` per entry), and
    ``metadata`` with generation context.
    """
    from autoinfo.output import _is_empty_summary  # noqa: PLC0415

    entries_list: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for section in report_data.sections:
        for item in section.items:
            url = item.get("source_url", "") or ""
            if url and url in seen_urls:
                continue
            # Defense-in-depth for issue #294: skip entries with empty title
            # or empty/placeholder summary.
            title = item.get("title", "")
            summary = item.get("summary", "")
            if not title.strip() or _is_empty_summary(summary):
                continue
            if url:
                seen_urls.add(url)
            entries_list.append(
                {
                    "title": title,
                    "summary": summary,
                    "url": url,
                    "source_url": url,
                    "source_type": item.get("source_type", ""),
                    "source_platform": item.get("source_label", "")
                    or item.get("source_platform", ""),
                    "date": item.get("collected_at", ""),
                    "domain": item.get("domain", ""),
                }
            )

    # Also include any references not already covered
    for ref in report_data.references:
        url = ref.get("source_url", "") or ""
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        entries_list.append(
            {
                "title": ref.get("title", ""),
                "summary": "",
                "url": url,
                "source_url": url,
                "source_type": ref.get("source_type", ""),
                "source_platform": ref.get("source_label", "") or ref.get("source_platform", ""),
                "date": "",
                "domain": ref.get("domain", ""),
            }
        )

    output = {
        "title": report_data.title,
        "summary": report_data.executive_summary,
        "key_findings": report_data.key_findings,
        "recommendations": report_data.recommendations,
        "entries": entries_list,
        "metadata": {
            "generated_at": report_data.generated_at,
            "domain": report_data.domain,
            "period": period,
            "format": "json",
            "entry_count": len(entries_list),
        },
    }
    return json.dumps(output, indent=2, ensure_ascii=False, default=str)


def _report_chapters(report_data: ReportData) -> list[tuple[str, str]]:
    """Split report data into ``(heading, markdown_body)`` chapters.

    Executive summary → "Executive Summary"; each themed section → its own
    chapter (content plus an item table when items exist); references →
    a "References" appendix.  Used by the ``epub`` and ``audiobook``
    report formats.
    """
    from autoinfo.output import _is_empty_summary  # noqa: PLC0415

    chapters: list[tuple[str, str]] = []
    if report_data.executive_summary:
        chapters.append(("Executive Summary", report_data.executive_summary))
    for idx, section in enumerate(report_data.sections, 1):
        body = section.content or ""
        if section.items:
            rows = ["| # | Title | Summary |", "|---|-------|---------|"]
            row_idx = 0
            for item in section.items:
                title = item.get("title", "")
                summary = item.get("summary", "")
                # Defense-in-depth for issue #294: skip empty-title rows
                # and rows with empty/placeholder summary.
                if not title.strip() or _is_empty_summary(summary):
                    continue
                row_idx += 1
                rows.append(f"| {row_idx} | {title} | {summary} |")
            if row_idx:
                body = f"{body}\n\n{chr(10).join(rows)}".strip()
        chapters.append((section.title or f"Section {idx}", body))
    if report_data.references:
        ref_lines = []
        for ref in report_data.references:
            line = f"- **{ref.get('title', '')}**"
            if ref.get("source_url"):
                line += f" \u2014 {ref['source_url']}"
            ref_lines.append(line)
        chapters.append(("References", "\n".join(ref_lines)))
    return chapters


def _render_report_template(report_data: ReportData, source_tier_badge: bool = True) -> str:
    """Render the report data through the Jinja2 template."""
    from autoinfo.output import TEMPLATE_PATH, _get_jinja_env  # noqa: PLC0415

    if not TEMPLATE_PATH.is_file():
        raise FileNotFoundError(f"Report template not found at {TEMPLATE_PATH}")

    template_source = TEMPLATE_PATH.read_text(encoding="utf-8")
    env = _get_jinja_env()
    template = env.from_string(template_source)

    report_marker = getattr(report_data, "grouping_degradation_marker", "")
    sections = [
        {
            "title": s.title,
            "content": s.content,
            "entries": s.items,
        }
        for s in report_data.sections
    ]
    if report_marker:
        # #120 (C4): the honest "grouped by source" marker leads the section
        # list when grouping degraded (LLM fail / chaos / no groups).
        sections.insert(0, {"marker": report_marker})

    return str(
        template.render(
            title=report_data.title,
            generated_at=report_data.generated_at,
            domain=report_data.domain,
            collection_id=report_data.collection_id,
            executive_summary=report_data.executive_summary,
            key_findings=report_data.key_findings,
            recommendations=report_data.recommendations,
            source_tier_badge=source_tier_badge,
            sections=sections,
            references=report_data.references,
            appendices=report_data.appendices,
        )
    )


def is_no_data_product(result: Any, format: str) -> bool:
    """True when a generated report is the no-curated-data empty shell.

    The pre-flight ``list_entries`` guard cannot detect this case:
    ``list_entries`` applies no tier filter, so unprocessed ``01-Raw`` rows
    satisfy it, while ``generate_report``'s product/empty/synthesized filters
    still drop every candidate and fall through to ``_render_empty_report``.
    Judging the rendered artifact instead of re-running the filter chain keeps
    this from drifting away from the generator's own behaviour.
    """
    from autoinfo.output import _NO_DATA_REPORT_MARKER  # noqa: PLC0415

    if format in ("json", "agent"):
        data = result
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (ValueError, TypeError):
                return False
        entries = data.get("entries") if isinstance(data, dict) else None
        return isinstance(entries, list) and not entries
    return isinstance(result, str) and _NO_DATA_REPORT_MARKER in result


def _render_empty_report(domain: str) -> str:
    """Return a brief message when there are no entries for *domain*."""
    from autoinfo.output import _domain_display_name  # noqa: PLC0415

    return (
        f"# {_domain_display_name(domain)} \u2014 Report\n\n"
        f"This edition has no curated items yet. Check back after the next collection run."
    )


def _render_empty_report_html(domain: str) -> str:
    """Return a minimal HTML5 document when there are no entries for *domain*."""
    from autoinfo.output import _get_jinja_env  # noqa: PLC0415

    env = _get_jinja_env()
    template = env.get_template("report.html.j2")
    return template.render(
        title=f"{domain} \u2014 Report",
        domain_name=domain,
        period="",
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        executive_summary="",
        executive_summary_html="",
        sections=[],
        references=[],
    )


def _render_report_html(report_data: ReportData, period: str = "weekly") -> str:
    """Render the report as a self-contained HTML5 document.

    Maps :class:`ReportData` to the variable contract expected by
    ``report.html.j2``:

    - ``title``, ``domain_name``, ``period``, ``generated_at`` — metadata
    - ``executive_summary`` / ``executive_summary_html`` — summary text
    - ``sections`` — list of ``{id, heading, content_html}``
    - ``references`` — list of ``{id, text, url}``

    Section ``content_html`` is built by converting the section's
    Markdown ``content`` plus its item table to HTML via the ``markdown``
    library.  References are numbered to match the template's ordered list.
    """
    from autoinfo.output import _get_jinja_env, _is_empty_summary  # noqa: PLC0415

    env = _get_jinja_env()
    template = env.get_template("report.html.j2")

    try:
        import markdown as md_lib  # noqa: PLC0415

        def _md_to_html(md_text: str) -> str:
            return str(md_lib.markdown(md_text or "", extensions=["fenced_code", "tables"]))
    except (ImportError, ModuleNotFoundError):

        def _md_to_html(md_text: str) -> str:
            return html.escape(md_text or "").replace("\n", "<br>\n")

    html_sections: list[dict[str, Any]] = []
    for idx, section in enumerate(report_data.sections, 1):
        content_md = section.content or ""
        if section.items:
            rows = ["| # | Title | Summary |", "|---|-------|---------|"]
            row_idx = 0
            for item in section.items:
                title = item.get("title", "")
                summary = item.get("summary", "")
                # Defense-in-depth for issue #294: skip rows with empty title
                # or empty/placeholder summary (rendered as blank cells).
                if not title.strip() or _is_empty_summary(summary):
                    continue
                row_idx += 1
                rows.append(f"| {row_idx} | {title} | {summary} |")
            if row_idx:
                content_md = (content_md + "\n\n" + "\n".join(rows)).strip()

        section_id = f"section-{idx}"
        html_sections.append(
            {
                "id": section_id,
                "heading": section.title,
                "content_html": _md_to_html(content_md),
            }
        )

    html_references: list[dict[str, Any]] = []
    for idx, ref in enumerate(report_data.references, 1):
        title = ref.get("title", "")
        platform = ref.get("source_label", "") or ref.get("source_platform", "")
        url = ref.get("source_url", "") or ""
        text = title
        if platform:
            text = f"{title} ({platform})" if title else platform
        html_references.append(
            {
                "id": f"ref-{idx}",
                "text": text,
                "url": url,
            }
        )

    exec_summary = report_data.executive_summary or ""
    exec_summary_html = _md_to_html(exec_summary) if exec_summary else ""

    from autoinfo.output.seo import generate_structured_data

    ld = generate_structured_data(
        title=report_data.title,
        description=exec_summary or report_data.title,
        date_published=report_data.generated_at,
        url="",
        article_type="Report",
    )
    structured_data = f'<script type="application/ld+json">\n{ld}\n</script>'

    return template.render(
        title=report_data.title,
        domain_name=report_data.domain,
        period=period,
        generated_at=report_data.generated_at,
        executive_summary=exec_summary,
        executive_summary_html=exec_summary_html,
        key_findings=report_data.key_findings,
        recommendations=report_data.recommendations,
        sections=html_sections,
        references=html_references,
        structured_data=structured_data,
    )


def _render_markdown(context: dict[str, Any]) -> str:
    """Render the Jinja2 digest template to Markdown."""
    from autoinfo.output import _get_jinja_env  # noqa: PLC0415

    env = _get_jinja_env()
    template = env.get_template("digest.md.j2")
    rendered = template.render(**context)
    marker = str(context.get("grouping_degradation_marker") or "")
    if marker and rendered:
        # #120 (C4): the honest "grouped by source" marker leads the digest
        # body when grouping degraded — a blockquote so it is visible but
        # clearly separate from the entry headings.
        rendered = f"{marker}\n\n{rendered}"
    # Issue #78: R4-uniform final decode — a single post-render pass strips
    # any residual HTML entities (&#039;/&amp;/&#8217;/...) that reached the
    # product despite the storage-layer decode (pre-#51 entries, bypassed
    # paths).  _decode_html_entities is idempotent (bounded iterative
    # html.unescape), so a legitimate literal "&amp;" becomes "&" — correct
    # for a consumer product.
    from autoinfo.kb import _decode_html_entities  # noqa: PLC0415

    rendered = _decode_html_entities(rendered)
    # Canonical EOF: one trailing newline (Jinja consumes the template's
    # final newline; pre-commit's end-of-file-fixer always re-adds one to
    # the golden fixture — the render must match byte-for-byte).
    return rendered.rstrip("\n") + "\n"


def _digest_chapters(context: dict[str, Any]) -> list[tuple[str, str]]:
    """Split digest context into ``(heading, markdown_body)`` chapters.

    Chapter 1 is front matter (title + metadata + executive summary); each
    KB entry becomes its own chapter.  Used by the ``epub`` and
    ``audiobook`` digest formats.
    """
    front_matter = [
        f"# {context.get('title', 'AutoInfo Digest')}",
        "",
        f"**Domain**: {context.get('domain', '')}",
        f"**Period**: {context.get('period_label', '')}",
        f"**Generated**: {context.get('generated_at', '')}",
    ]
    llm_synthesis = context.get("llm_synthesis") or {}
    if llm_synthesis.get("executive_summary"):
        front_matter.extend(
            [
                "",
                "## Executive Summary",
                "",
                str(llm_synthesis["executive_summary"]),
            ]
        )
    chapters: list[tuple[str, str]] = [("Front Matter", "\n".join(front_matter))]
    for entry in context.get("entries") or []:
        chapters.append(
            (
                str(entry.get("title", "Untitled")),
                str(entry.get("summary", "") or ""),
            )
        )
    return chapters


def _render_html(markdown_text: str) -> str:
    """Convert Markdown to plain HTML (no CSS styling).

    Uses the ``markdown`` library (already a project dependency) to
    produce bare HTML without any stylesheets or CSS classes.

    .. deprecated::
        Prefer :func:`_render_digest_html` for digest output, which
        renders a full HTML5 document via ``digest.html.j2``.  This
        helper is retained for backward compatibility with callers
        that pass raw Markdown.
    """
    try:
        import markdown as md_lib  # noqa: PLC0415

        return str(md_lib.markdown(markdown_text, extensions=["fenced_code", "tables"]))
    except (ImportError, ModuleNotFoundError):
        logger.warning("markdown library not available \u2014 returning raw markdown")
        return markdown_text


def _render_digest_html(context: dict[str, Any]) -> str:
    """Render the digest as a self-contained HTML5 document.

    Maps the internal digest context (built by :func:`generate_digest`)
    to the variable contract expected by ``digest.html.j2``:

    - ``title`` — digest title
    - ``domain_name`` — domain identifier
    - ``period`` — human-readable period label with date range
    - ``generated_at`` — ISO timestamp
    - ``executive_summary`` — LLM-synthesized summary (if any)
    - ``key_findings`` — list of ``{title, text}`` dicts (ranked by order)
    - ``trends`` — list of trend strings
    - ``recommendations`` — list of recommendation strings
    - ``entries`` — list of ``{title, source_url, summary, relevance_score}``
    """
    from autoinfo.output import _get_jinja_env  # noqa: PLC0415

    env = _get_jinja_env()
    template = env.get_template("digest.html.j2")

    synthesis = context.get("llm_synthesis") or {}

    # Map LLM key_findings ({topic, detail}) -> {title, text}; also
    # accepts {text, source_url} objects and plain strings (issue #279
    # fallback shape), threading source_url through for inline citation.
    key_findings: list[dict[str, Any]] = []
    for f in synthesis.get("key_findings") or []:
        if isinstance(f, dict):
            topic = str(f.get("topic") or "").strip()
            detail = str(f.get("detail") or "").strip()
            text = str(f.get("text") or "").strip()
            item = {"title": topic, "text": detail or text or topic}
            item["source_url"] = str(f.get("source_url") or "").strip()
        elif isinstance(f, str):
            item = {"title": "", "text": f.strip(), "source_url": ""}
        else:
            continue
        if item["text"]:
            key_findings.append(item)

    # Map KB entries to the template's entry contract
    html_entries = [
        {
            "title": e.get("title", ""),
            "source_url": e.get("source_url", "") or "",
            "summary": e.get("summary", "") or "",
            "relevance_score": e.get("relevance_score"),
            "source_tier": e.get("source_tier"),
        }
        for e in (context.get("entries") or [])
    ]

    period_label = context.get("period_label", "")
    date_from = context.get("date_from", "")
    date_to = context.get("date_to", "")
    period_str = f"{period_label} ({date_from} \u2013 {date_to})" if period_label else ""

    from autoinfo.output.seo import generate_structured_data

    ld = generate_structured_data(
        title=context.get("title", ""),
        description=synthesis.get("executive_summary", "") or context.get("title", ""),
        date_published=context.get("generated_at", ""),
        url="",
        article_type="Article",
    )
    structured_data = f'<script type="application/ld+json">\n{ld}\n</script>'

    rendered = template.render(
        title=context.get("title", ""),
        domain_name=context.get("domain", ""),
        period=period_str,
        generated_at=context.get("generated_at", ""),
        executive_summary=synthesis.get("executive_summary", "") or "",
        key_findings=key_findings,
        trends=synthesis.get("trends") or [],
        recommendations=synthesis.get("recommendations") or [],
        entries=html_entries,
        structured_data=structured_data,
    )
    # Issue #78: R4-uniform final decode for the HTML surface (see
    # _render_markdown).
    from autoinfo.kb import _decode_html_entities  # noqa: PLC0415

    return _decode_html_entities(rendered)


def _render_json(context: dict[str, Any]) -> str:
    """Render the digest as a JSON string.

    The JSON structure separates metadata, LLM synthesis, and entries
    so consumers can parse with full fidelity.
    """
    output = {
        "digest_type": "digest",
        "domain": context["domain"],
        "period": context["period"],
        "period_label": context["period_label"],
        "date_from": context["date_from"],
        "date_to": context["date_to"],
        "generated_at": context["generated_at"],
        "entry_count": len(context["entries"]),
        "llm_synthesis": context["llm_synthesis"],
        "entries": context["entries"],
    }
    return json.dumps(output, indent=2, ensure_ascii=False, default=str)


def _render_agent_json(
    entries: list[dict[str, Any]],
    context: dict[str, Any],
) -> str:
    """Render entries as agent-native JSON-LD (``@type: KnowledgeDigest``).

    Produces a structured JSON-LD payload optimized for LLM re-consumption.
    Agents can parse, re-synthesize, store in their own KB, or combine
    with other data sources.

    Parameters
    ----------
    entries:
        List of KB entry dicts (from :meth:`KBStore.list_entries`).
        Expected keys: ``entry_id``, ``title``, ``summary``, ``source_url``,
        ``source_platform``, ``collected_at``, ``relevance_score``, ``tags``.
    context:
        Rendering context dict.  Expected keys: ``domain``, ``period``,
        ``generated_at``, ``llm_synthesis``, ``target_audience``.

    Returns
    -------
    str
        Indented JSON-LD string.
    """
    import re

    from autoinfo.output import _JSONLD_DIGEST, _PRODUCT_ANALYSIS_FIELDS  # noqa: PLC0415

    generated_at = context.get("generated_at", datetime.now(timezone.utc).isoformat())
    domain = context.get("domain", "")
    period = context.get("period", "")
    target_audience = context.get("target_audience", "")
    llm_synthesis = context.get("llm_synthesis", {})

    # --- Build entry list ----------------------------------------------------
    agent_entries: list[dict[str, Any]] = []
    for e in entries:
        entry_uuid = e.get("entry_id", "")
        tags: list[str] = []
        tags_raw = e.get("tags", "")
        if isinstance(tags_raw, list):
            tags = tags_raw
        elif isinstance(tags_raw, str):
            try:
                tags = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                tags = [tags_raw] if tags_raw else []

        # Derive entities from tags
        entities = [{"name": tag, "type": "topic", "relation": "tagged"} for tag in tags]

        # Confidence score: use relevance_score/100 as proxy if available
        relevance = e.get("relevance_score")
        if relevance is not None:
            try:
                confidence = round(float(relevance) / 100.0, 4)
            except (ValueError, TypeError):
                confidence = None
        else:
            confidence = None

        # Key points: split summary into sentences as approximate key points
        summary = e.get("summary", "") or ""
        key_points: list[str] = []
        if summary:
            sentences = re.split(r"(?<=[.!?])\s+", summary.strip())
            key_points = [s.strip() for s in sentences[:3] if s.strip()]

        agent_entries.append(
            {
                "uuid": entry_uuid,
                "title": e.get("title", ""),
                "tl_dr": summary,
                "source_url": e.get("source_url", ""),
                "source_platform": e.get("source_label") or e.get("source_platform", ""),
                "collected_at": e.get("collected_at", ""),
                "relevance_score": e.get("relevance_score"),
                "confidence_score": confidence,
                "key_points": key_points,
                "entities": entities,
            }
        )

    # --- Build trends from LLM synthesis --------------------------------------
    trends: list[dict[str, Any]] = []
    for trend in llm_synthesis.get("trends", []):
        if isinstance(trend, str):
            trends.append({"topic": trend, "direction": "", "evidence": ""})
        elif isinstance(trend, dict):
            trends.append(trend)
    # Also pull from key_findings
    for finding in llm_synthesis.get("key_findings", []):
        topic = finding.get("topic", "") if isinstance(finding, dict) else str(finding)
        if topic and not any(t.get("topic") == topic for t in trends):
            detail = finding.get("detail", "") if isinstance(finding, dict) else ""
            trends.append({"topic": topic, "direction": "observed", "evidence": detail})

    # --- Build metadata -------------------------------------------------------
    metadata: dict[str, Any] = {
        "entry_count": len(entries),
        "generated_at": generated_at,
        "domain": domain,
    }
    if period:
        metadata["period"] = period

    # --- Assemble JSON-LD payload ---------------------------------------------
    output: dict[str, Any] = {
        **_JSONLD_DIGEST,
        "uuid": str(uuid.uuid4()),
        "generated_at": generated_at,
        "domain": domain,
        "period": period,
        "target_audience": target_audience or None,
        "entries": agent_entries,
        "trends": trends,
        "metadata": metadata,
    }
    # Surface the per-product analysis fields (todo 22) — implications /
    # risks / action_required / key_metrics — copied from the synthesis so a
    # downstream agent can query/filter them. Emitted only when populated,
    # so default digest/report agent output stays unchanged.
    for synthesis_field in _PRODUCT_ANALYSIS_FIELDS:
        if llm_synthesis.get(synthesis_field):
            output[synthesis_field] = llm_synthesis[synthesis_field]

    return json.dumps(output, indent=2, ensure_ascii=False, default=str)
