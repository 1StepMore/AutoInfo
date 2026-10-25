"""Extracted from :mod:`autoinfo.output` (#582 phase 2): presentation products."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from autoinfo.config import Config
    from autoinfo.output.contracts import DeliveryOutput as DeliveryOutput
    from autoinfo.output.contracts import _DeliveryGatesBypass as _DeliveryGatesBypass

import logging

logger = logging.getLogger("autoinfo.output")


def generate_presentation(
    domain: str,
    topic: str,
    slide_count: int = 10,
    target_audience: str = "executive",
    format: str = "markdown",
    custom_instructions: str = "",
    user_id: str = "",
    allow_empty: bool = False,
    delivery_gate_configs: dict[str, dict[str, Any]] | _DeliveryGatesBypass | None = None,
    llm_config: Config | None = None,
    language: str = "",
    include_stale: bool = False,
) -> str | DeliveryOutput:
    """Generate a slide-based presentation for *topic* within *domain*.

    Searches the KB for entries related to *topic*, asks the LLM to
    produce structured slide content, and renders through the
    appropriate template based on *format*.

    ``allow_empty`` bypasses the empty-shell guard (#182). Unit tests that
    stub the LLM (returning no slides) use it to exercise prompt-building /
    content-preference logic; production callers leave it False so an empty
    presentation raises instead of shipping a 240-byte shell.

    Parameters
    ----------
    domain : str
        Domain to scope the presentation to (e.g. ``"medical-research"``).
    topic : str
        Presentation topic — used to filter relevant KB entries.
    slide_count : int, optional
        Desired number of slides (default 10, range 3–30).
    target_audience : str, optional
        Intended audience.  One of ``"researcher"``, ``"clinician"``,
        ``"executive"`` (default), ``"student"``.
    format : str, optional
        Output format (default ``"markdown"``).  Supported values:

        - ``"markdown"`` — Reveal.js-flavoured Markdown via
          ``presentation.md.j2`` (backward compatible).
        - ``"html"`` — standalone Reveal.js HTML5 document via
          ``presentation.html.j2`` (loads Reveal.js from CDN).
        - ``"mkslides"`` — generate mkslides-compatible Markdown and
          attempt to build via the ``mkslides`` CLI; falls back to
          standalone HTML when mkslides is unavailable.

    custom_instructions : str, optional
        Optional string of additional instructions to append to the LLM
        generation prompt.  Ignored when empty/absent.
    user_id : str, optional
        Optional end-user ID.  When non-empty, the user's stored
        ``content_preference`` (from
        :func:`autoinfo.user_store.get_preferences`) is auto-loaded and
        KB entries are tier-filtered accordingly (B-001).  When empty
        (default), behavior is unchanged and all tiers are included.

    Returns
    -------
    str
        Rendered presentation string.

    Raises
    ------
    ValueError
        If *format*, *target_audience*, or *slide_count* is invalid.
    """
    from autoinfo.output import (
        KBStore,
        _call_llm_for_presentation,
        _filter_entries_by_content_preference,
        _filter_product_entries,
        _filter_stale_entries,
        _fire_agent_notification,
        _resolve_content_preference,
        _sanitize_presentation_sources,
        _select_story_set,
    )
    from autoinfo.output.audience import _AUDIENCE_DESCRIPTIONS as _AUDIENCE_DESCRIPTIONS
    from autoinfo.output.audience import _VALID_AUDIENCES as _VALID_AUDIENCES
    from autoinfo.output.contracts import DeliveryOutput as DeliveryOutput
    from autoinfo.output.contracts import StaleSourceError as StaleSourceError
    from autoinfo.output.entries import (
        _filter_entries_by_domain_exclusions as _filter_entries_by_domain_exclusions,
    )
    from autoinfo.output.entries import (
        _filter_entries_by_language_product_safe as _filter_entries_by_language_product_safe,
    )
    from autoinfo.output.entries import _resolve_effective_language as _resolve_effective_language
    from autoinfo.output.gates import _apply_delivery_gates as _apply_delivery_gates
    from autoinfo.output.gates import _apply_min_content_guard as _apply_min_content_guard
    from autoinfo.output.gates import (
        _resolve_delivery_gate_configs as _resolve_delivery_gate_configs,
    )
    from autoinfo.output.sources import _filter_drifted_entries as _filter_drifted_entries

    if format not in ("markdown", "html", "mkslides", "agent"):
        raise ValueError(
            f"Unsupported output format: {format!r}. Supported: markdown, html, mkslides, agent"
        )

    if target_audience not in _VALID_AUDIENCES:
        raise ValueError(
            f"Invalid target_audience '{target_audience}'. "
            f"Must be one of: {', '.join(sorted(_VALID_AUDIENCES))}"
        )

    slide_count = max(3, min(30, slide_count))
    # Issue #182: an empty target_audience renders a blank "Audience:" line;
    # default to executive so the deck header is always populated.
    target_audience = (target_audience or "").strip() or "executive"

    # --- Resolve delivery-gate config (issue #298: default-on in production) --
    delivery_gate_configs = _resolve_delivery_gate_configs(domain, delivery_gate_configs)

    # -- Load KB entries related to topic --------------------------------
    kb_store = KBStore()
    # Single-domain story set — shared with digest/report (#119).  This is the
    # intended behavior change: the presentation's entry universe narrows from
    # all-time (limit=5000, no window) to the same-week shared set, so a deck
    # and its digest/report reference the same stories.
    entries, _date_range, _period_was_empty = _select_story_set(
        kb_store,
        domain,
        period="weekly",
        product="presentation",
        query_limit=5000,
    )

    # --- Content-preference tier filtering (B-001) ---------------------------
    content_preference: str = _resolve_content_preference(user_id)
    if content_preference != "both":
        filtered_entries = _filter_entries_by_content_preference(entries, content_preference)
        if len(filtered_entries) != len(entries):
            logger.info(
                "Excluded %d entries from presentation for domain '%s' "
                "due to content_preference='%s'",
                len(entries) - len(filtered_entries),
                domain,
                content_preference,
            )
        entries = filtered_entries

    # --- Test/empty entry filtering (issue #298 — layer 1) -------------------
    entries = _filter_product_entries(entries)

    # --- Selection-time source-drift filter (#119) ---------------------------
    # Entries whose source identity is absent from the domain's CURRENT config
    # source list are excluded here (before topic relevance), so a removed
    # source never reaches the LLM prompt nor the KB-derived slides.  FAIL-OPEN
    # on an unreadable config: excludes nothing.  Never deletes KB entries.
    entries = _filter_drifted_entries(entries, domain)

    # --- Per-domain exclude_keywords filter (issue #319) ---------------------
    # Cross-domain noise guard: drop entries matching their own domain's
    # exclude_keywords blacklist BEFORE topic relevance filtering / LLM
    # synthesis / KB-derived slides.
    entries = _filter_entries_by_domain_exclusions(entries, domain)

    # --- Language filter (issue #309 / #317 / #15) ---------------------------
    # Mirror digest/report: when a user requests a specific language (or a
    # domain declares a default_language), drop entries in other languages so
    # a presentation is internally consistent (no zh/en interleave).  Without
    # this, the #8 Chinese financial noise (沪指/创业板/A股) leaked into
    # ai-commercial presentations via topic_entries and the KB-derived
    # fallback slides.  An explicit param wins; otherwise the domain default
    # fills in.
    effective_language = _resolve_effective_language(language, domain)
    if effective_language:
        entries, _ = _filter_entries_by_language_product_safe(entries, effective_language)

    # --- Staleness filter (backup #60) ---------------------------------------
    # Teaching-layer products must never silently regenerate from an old
    # corpus after a source swap; mirror the digest freshness filter.
    prior_count = len(entries)
    entries = _filter_stale_entries(
        entries, domain, include_stale=include_stale, product="presentation"
    )
    if not include_stale and prior_count > 0 and not entries and not allow_empty:
        raise StaleSourceError(
            f"All {prior_count} candidate entries for domain '{domain}' are stale. "
            f"Refusing to generate an empty-shell presentation from old corpus. "
            f"Re-run collection to refresh the source, or pass include_stale=true."
        )

    # Filter entries by topic relevance (title/summary contains topic terms)
    topic_terms = topic.lower().split()
    topic_entries = [
        e
        for e in entries
        if any(
            term in (e.get("title", "") + " " + e.get("summary", "")).lower()
            for term in topic_terms
        )
    ]

    if not topic_entries:
        # Fall back to all entries for the domain
        topic_entries = entries[:50]

    # -- Build LLM prompt -------------------------------------------------
    audience_desc = _AUDIENCE_DESCRIPTIONS.get(target_audience, "general audience")
    # Cap KB entries sent to the LLM: DeepSeek-V4-Flash is a reasoning
    # model — a long prompt burns max_tokens on reasoning_content and
    # emits empty/truncated content (issue #178). 10 representative
    # entries (title + summary) keep the prompt well under the safe
    # threshold while still grounding the deck in domain facts.
    # Each entry carries its real source_url (mirroring tutorial/report) so
    # the LLM can only cite verifiable URLs — never fabricated placeholders
    # (backup issue #101).
    entry_summaries = "\n".join(
        f"- {e.get('title', '?')}: {e.get('summary', '(no summary)')[:220]}"
        + (f" (Source: {e['source_url']})" if e.get("source_url") else "")
        for e in topic_entries[:10]  # cap entries sent to LLM (#178)
    )

    prompt = (
        f"You are a presentation designer creating a slide deck for a "
        f"{target_audience} audience ({audience_desc}). "
        f"Topic: {topic}\n\n"
        "Given the following knowledge base entries, generate slide content. "
        f"Aim for approximately {slide_count} slides.\n"
        "Return a JSON object with the following fields:\n"
        '  - "title": presentation title (string)\n'
        '  - "description": one-sentence description (string)\n'
        '  - "slides": array of slide objects, each with:\n'
        '      - "title": slide heading\n'
        '      - "content": 2-4 sentence slide body\n'
        '      - "bullets": array of 2-5 bullet points (strings)\n'
        '      - "notes": speaker notes (string, optional — may be null)\n\n'
        f"KB Entries:\n{entry_summaries}\n\n"
        "Return all fields in a single JSON object. Adapt depth and terminology "
        f"specifically for a {target_audience} audience.\n"
        "When a claim comes from a specific KB entry, end that bullet with "
        '" (Source: <the exact http(s) entry URL>)". '
        'NEVER write "Source: KB:", "Source: KB-N", "knowledgebase.local", '
        '"knowledgebase.example.com", or a bare publication/person name as '
        "a source — every (Source: ...) must be a real http(s) URL from the "
        "KB Entries list above."
    )

    if custom_instructions:
        prompt += f"\n\nAdditional instructions: {custom_instructions}"

    llm_result = _call_llm_for_presentation(prompt, slide_count)

    # -- Build template context -------------------------------------------
    # Issue #149: day-granularity timestamp (no microseconds), matching #138.
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    context = {
        "title": llm_result.get("title", f"{topic} — Presentation"),
        "topic": topic,
        "domain": domain,
        "target_audience": target_audience,
        "description": llm_result.get("description", ""),
        "slides": llm_result.get("slides", []),
        "generated_at": generated_at,
    }

    # Issue #182 audit-feedback: a presentation with zero slides or only a
    # header stub (LLM empty-content, DeepSeek #178) must NOT be persisted.
    # Raise so callers skip the artifact instead of shipping a 240-byte shell.
    # Applies to markdown AND agent: agent previously returned the JSON-LD
    # shell directly (slides=[]), producing 13 empty presentation-agent
    # artifacts in the 2026-08-11 fill run.
    slides = llm_result.get("slides") or []
    if not slides:
        # Issue #220: LLM synthesis returned no usable slides (DeepSeek
        # empty/partial content).  Fall back to KB-derived slides so the
        # deck carries real domain content instead of failing or shipping
        # an empty shell.  Content is drawn verbatim from KB entries —
        # never fabricated.
        slides = _fallback_slides_from_entries(topic_entries, slide_count)
        if slides:
            llm_result = dict(llm_result)
            llm_result["slides"] = slides
            context["slides"] = slides
            if not context.get("description"):
                context["description"] = (
                    f"KB-derived presentation for {domain} ({len(slides)} slides)"
                )
    # Render the markdown form purely as a content-completeness check for
    # agent output (same template context, same content).
    rendered = _render_presentation_template(context, format=format)
    rendered_check = (
        _render_presentation_template(context, format="markdown") if format == "agent" else rendered
    )
    # Issue #93: strip fabricated (non-URL) source citations from the
    # rendered markdown/html/mkslides deck — the LLM may substitute names
    # for URLs even when prompted otherwise.  Agent JSON-LD is untouched
    # (its sources are real URLs from topic_entries).
    # Issue #101 backstop: only real KB source_urls may appear in the deck.
    # Every (Source: URL) is cross-checked against this whitelist so a
    # well-formed but fabricated placeholder (https://www.news.com/<slug>,
    # https://example.com/kb/N) never ships.
    all_source_urls = {
        str(e["source_url"]).strip()
        for e in topic_entries
        if str(e.get("source_url") or "").strip()
    }
    if format != "agent":
        rendered = _sanitize_presentation_sources(rendered, allowed_urls=all_source_urls)
    rendered_check = _sanitize_presentation_sources(rendered_check, allowed_urls=all_source_urls)
    if not allow_empty and (len(slides) < 1 or len(rendered_check.strip()) < 500):
        raise ValueError(
            f"Presentation generation produced no usable content for "
            f"domain={domain!r} topic={topic!r} (slides={len(slides)}, "
            f"chars={len(rendered_check.strip())})"
        )

    # -- Agent-native JSON-LD format ----------------------------------------
    if format == "agent":
        return _render_presentation_agent_json(
            llm_result, domain, topic, target_audience, generated_at, topic_entries
        )  # noqa: E501

    # --- Delivery gates (D1-D3) ---------------------------------------------
    if delivery_gate_configs is not None:
        result = _apply_delivery_gates(
            rendered_output=rendered,
            output_format=format,
            entries=entries,
            context=context,
            product_type="presentation",
            delivery_gate_configs=delivery_gate_configs,
            llm_config=llm_config,
        )
        result = _apply_min_content_guard(result, entries, "presentation")
        _fire_agent_notification(
            "new_presentation",
            result.output if isinstance(result, DeliveryOutput) else rendered,
            product_id=f"{domain}-presentation",
        )
        return result

    return rendered


def _render_presentation_agent_json(
    llm_result: dict[str, Any],
    domain: str,
    topic: str,
    target_audience: str,
    generated_at: str,
    topic_entries: list[dict[str, Any]],
) -> str:
    """Render presentation data as agent-native JSON-LD (``@type: KnowledgePresentation``)."""
    from autoinfo.output.contracts import _JSONLD_PRESENTATION as _JSONLD_PRESENTATION

    slides: list[dict[str, Any]] = []
    for s in llm_result.get("slides", []):
        slides.append(
            {
                "title": s.get("title", ""),
                "content": s.get("content", ""),
                "bullets": s.get("bullets", []),
                "notes": s.get("notes"),
            }
        )

    sources: list[dict[str, Any]] = []
    for e in topic_entries[:50]:
        sources.append(
            {
                "entry_id": e.get("entry_id", ""),
                "title": e.get("title", ""),
                "source_url": e.get("source_url", ""),
            }
        )

    output: dict[str, Any] = {
        **_JSONLD_PRESENTATION,
        "uuid": str(uuid.uuid4()),
        "title": llm_result.get("title", f"{topic} — Presentation"),
        "topic": topic,
        "domain": domain,
        "target_audience": target_audience,
        "description": llm_result.get("description", ""),
        "theme": "default",
        "slides": slides,
        "sources": sources,
        "generated_at": generated_at,
        "metadata": {
            "slide_count": len(slides),
            "source_count": len(sources),
        },
    }
    return json.dumps(output, indent=2, ensure_ascii=False, default=str)


def _fallback_slides_from_entries(
    entries: list[dict[str, Any]],
    slide_count: int,
) -> list[dict[str, Any]]:
    """Build KB-derived slides when LLM synthesis returns no usable slides.

    Issue #220: DeepSeek occasionally returns empty/partial presentation
    content.  Rather than failing (or shipping an empty shell), fall back
    to slides drawn verbatim from KB entries — one slide per entry (capped
    at *slide_count*).  Content is real domain material, never fabricated.
    """

    slides: list[dict[str, Any]] = []
    for e in entries[:slide_count]:
        title = _truncate_ellipsis(str(e.get("title") or "Untitled"), 80)
        # Issue #149: entries filtered by topic/language/staleness may carry
        # an empty summary — fall back to the entry content (first ~600
        # chars) so the KB-derived slides never yield an empty shell.
        summary = str(e.get("summary") or "").strip()
        if not summary:
            content = str(e.get("content") or "").strip()
            summary = _truncate_ellipsis(content, 600) if content else ""
        if not summary:
            continue
        # Issue #182: naive ``summary.split(".")`` destroys currency decimals
        # ($8.5 billion → $8 / "5 billion").  Split on sentence boundaries
        # (end-punctuation followed by whitespace or end-of-string) so monetary
        # figures like $8.5 billion and $1.1 billion stay intact.
        bullets = _split_summary_sentences(summary)[:3]
        slides.append(
            {
                "title": title,
                "content": _truncate_ellipsis(summary, 600),
                "bullets": bullets,
                "notes": "Prepared from knowledge base sources.",
                "source_url": str(e.get("source_url") or "").strip(),
            }
        )
        if len(slides) >= slide_count:
            break
    return slides


def _call_llm_for_presentation(prompt: str, slide_count: int) -> dict[str, Any]:
    """Call LiteLLM to generate structured presentation content."""
    from autoinfo.output import (
        Config,
        _parse_json_response,
        call_with_fallback,
        get_config_path,
        get_prompt,
        load_config,
    )

    config_path = get_config_path()
    if config_path and config_path.is_file():
        try:
            config = load_config(config_path)
        except Exception:
            config = Config()
    else:
        config = Config()

    model = config.llm.resolve_model()
    full_model = model

    try:
        response = call_with_fallback(
            model=full_model,
            messages=[
                {
                    "role": "system",
                    "content": get_prompt("presentation_system"),
                },
                {"role": "user", "content": prompt},
            ],
            json_mode=config.llm.json_mode and not config.llm.reasoning_model,
            max_tokens=8000,
            temperature=0.1,
            api_key=config.llm.api_key or None,
            base_url=config.llm.base_url or None,
        )
    except Exception as exc:
        logger.error("LLM presentation synthesis failed: %s", exc)
        return {}
    content: str = response.choices[0].message.content or ""
    return _parse_json_response(content)


def _render_presentation_template(
    context: dict[str, Any],
    format: str = "markdown",
) -> str:
    """Render the presentation data through the appropriate template.

    Parameters
    ----------
    context:
        Template context dict built by :func:`generate_presentation`.
    format:
        Output format — ``"markdown"`` (default, backward compatible),
        ``"html"`` (standalone Reveal.js HTML5 via CDN), or
        ``"mkslides"`` (mkslides-compatible Markdown with optional
        CLI build; falls back to standalone HTML on failure).
    """
    from autoinfo.output import _render_presentation_html
    from autoinfo.output.templating import _get_jinja_env as _get_jinja_env

    if format == "html":
        return _render_presentation_html(context)

    if format == "mkslides":
        return _render_presentation_mkslides(context)

    # Default: backward-compatible Markdown
    env = _get_jinja_env()
    template = env.get_template("presentation.md.j2")
    return template.render(**context)


def _render_presentation_html(context: dict[str, Any]) -> str:
    """Render the presentation as a standalone Reveal.js HTML5 document.

    Loads Reveal.js CSS/JS from the jsdelivr CDN — no bundling.
    The template (``presentation.html.j2``) is autoescaped by
    :func:`_html_autoescape` because of its ``.html.j2`` extension.
    """
    from autoinfo.output.templating import _get_jinja_env as _get_jinja_env

    env = _get_jinja_env()
    template = env.get_template("presentation.html.j2")
    return template.render(**context)


def _render_presentation_mkslides(context: dict[str, Any]) -> str:
    """Render the presentation as mkslides-compatible Markdown.

    Produces a Markdown file with YAML frontmatter (``title``,
    ``author``, ``theme``) and ``---`` slide separators, writes it to
    a temporary directory, and attempts to build via the ``mkslides``
    CLI.  When mkslides is not installed or the build fails, falls
    back to the standalone HTML renderer with a log warning.
    """
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    from autoinfo.output import _render_presentation_html

    title = context.get("title", "Presentation")
    author = context.get("domain", "AutoInfo")
    theme = context.get("theme", "black")
    slides = context.get("slides", []) or []

    # Build mkslides Markdown: frontmatter + --- separated slides
    lines: list[str] = [
        "---",
        f"title: {title}",
        f"author: {author}",
        f"theme: {theme}",
        "---",
        "",
    ]

    for slide in slides:
        slide_title = slide.get("title", "")
        slide_content = slide.get("content", "")
        bullets = slide.get("bullets", []) or []
        notes = slide.get("notes", "")

        lines.append(f"# {slide_title}")
        lines.append("")
        if slide_content:
            lines.append(slide_content)
            lines.append("")
        if bullets:
            for b in bullets:
                lines.append(f"- {b}")
            lines.append("")
        if notes:
            lines.append(f"<!-- {notes} -->")
            lines.append("")

        lines.append("---")
        lines.append("")

    mkslides_md = "\n".join(lines)

    # Attempt mkslides build in a temp directory
    try:
        with tempfile.TemporaryDirectory(prefix="autoinfo-mkslides-") as tmpdir:
            src_path = Path(tmpdir) / "presentation.md"
            src_path.write_text(mkslides_md, encoding="utf-8")

            try:
                proc = subprocess.run(
                    ["mkslides", "build", "presentation.md"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except FileNotFoundError:
                logger.warning(
                    "mkslides is not installed — falling back to standalone HTML presentation."
                )
                return _render_presentation_html(context)
            except subprocess.TimeoutExpired:
                logger.warning(
                    "mkslides build timed out after 30s — falling back "
                    "to standalone HTML presentation."
                )
                return _render_presentation_html(context)

            if proc.returncode != 0:
                logger.warning(
                    "mkslides build failed (rc=%d): %s — falling back "
                    "to standalone HTML presentation.",
                    proc.returncode,
                    (proc.stderr or "").strip()[:200],
                )
                return _render_presentation_html(context)

            # mkslides writes output to a default location; locate the HTML
            out_dir = Path(tmpdir) / "public"
            html_candidates = sorted(out_dir.rglob("*.html")) if out_dir.is_dir() else []
            if not html_candidates:
                # Some mkslides versions write alongside the source
                html_candidates = sorted(Path(tmpdir).glob("*.html"))

            if not html_candidates:
                logger.warning(
                    "mkslides build produced no HTML output — falling "
                    "back to standalone HTML presentation."
                )
                return _render_presentation_html(context)

            return html_candidates[0].read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning(
            "mkslides rendering failed (%s) — falling back to standalone HTML presentation.",
            exc,
        )
        return _render_presentation_html(context)


def _split_summary_sentences(text: str) -> list[str]:
    """Split *text* into sentences on end-punctuation boundaries.

    Unlike a naive ``str.split(".")``, this preserves decimal points in
    monetary figures (issue #182: ``$8.5 billion`` must not become
    ``$8`` / ``5 billion``).  We split only on ``.``/``!``/``?`` that are
    followed by whitespace (or end of string) and then trim leftover dots.
    """
    parts = re.split(r"(?<=[.?!])(?=[ \t\n\r])|(?<=[.?!])$", text)
    sentences: list[str] = []
    for part in parts:
        cleaned = part.strip().rstrip(".")
        if cleaned:
            sentences.append(cleaned)
    return sentences


def _truncate_ellipsis(text: str, limit: int) -> str:
    """Truncate *text* to at most *limit* chars, never cutting mid-word.

    Returns *text* unchanged when it fits within *limit*.  Otherwise
    returns the longest prefix that ends on a complete word within the
    limit and appends ``…`` to signal truncation.  Because we only ever
    break on whitespace, monetary figures like ``$8.5 billion`` stay
    intact (issue #201).  Falls back to a hard cut when a single word
    alone exceeds *limit* (no earlier break exists).
    """
    if len(text) <= limit:
        return text
    head = text[:limit]
    break_at = max(head.rfind(" "), head.rfind("\t"), head.rfind("\n"))
    if break_at > 0:
        head = head[:break_at].rstrip()
    return head + "…"
