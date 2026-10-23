"""Extracted from :mod:`autoinfo.output` (#582 phase 2): tutorial products."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from autoinfo.config import Config
    from autoinfo.output import DeliveryOutput, _DeliveryGatesBypass

import logging

logger = logging.getLogger(__name__)


def generate_tutorial(
    domain: str,
    collection_id: str | None = None,
    target_audience: str = "student",
    format: str = "markdown",
    custom_instructions: str = "",
    user_id: str = "",
    delivery_gate_configs: dict[str, dict[str, Any]] | _DeliveryGatesBypass | None = None,
    llm_config: Config | None = None,
    include_stale: bool = False,
) -> str | DeliveryOutput:
    """Generate a structured tutorial for *domain*, adapted to *target_audience*.

    Fetches KB entries, asks the LLM to structure a learning path with
    objectives, content sections, and exercises, then renders the result
    through ``tutorial.md.j2``.

    Parameters
    ----------
    domain : str
        Domain to generate the tutorial for (e.g. ``"medical-research"``).
    collection_id : str, optional
        Optional collection ID to scope the tutorial to a specific
        collection run.  When omitted, all KB entries for the domain
        are included.
    target_audience : str
        Intended audience for the tutorial.  One of ``"researcher"``,
        ``"clinician"``, ``"executive"``, ``"student"`` (default).
    format : str, optional
        Output format (default ``"markdown"``).  Only ``"markdown"``
        is currently supported.
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
        Rendered tutorial string.

    Raises
    ------
    ValueError
        If *format* or *target_audience* is unsupported.
    """
    from autoinfo.output import (  # noqa: PLC0415
        _AUDIENCE_DESCRIPTIONS,
        _JSONLD_TUTORIAL,
        _VALID_AUDIENCES,
        DeliveryOutput,
        KBStore,
        StaleSourceError,
        _apply_delivery_gates,
        _apply_min_content_guard,
        _build_tutorial_json_prompt,
        _build_tutorial_markdown_prompt,
        _call_llm_for_tutorial,
        _domain_display_name,
        _ensure_tutorial_complete,
        _filter_entries_by_content_preference,
        _filter_entries_by_domain_exclusions,
        _filter_foreign_language_teaching_entries,
        _filter_product_entries,
        _filter_stale_entries,
        _fire_agent_notification,
        _is_lang_learning_domain,
        _render_tutorial_agent_json,
        _render_tutorial_template,
        _resolve_content_preference,
        _resolve_delivery_gate_configs,
        _resolve_effective_language,
        _resolve_gloss_language,
        _seed_domain_default_language,
        _try_notify_content_ready,
        _tutorial_has_content,
    )

    if format not in ("markdown", "agent"):
        raise ValueError(f"Unsupported output format: {format!r}. Supported: markdown, agent")

    if target_audience not in _VALID_AUDIENCES:
        raise ValueError(
            f"Invalid target_audience '{target_audience}'. "
            f"Must be one of: {', '.join(sorted(_VALID_AUDIENCES))}"
        )

    # --- Resolve delivery-gate config (issue #298: default-on in production) --
    delivery_gate_configs = _resolve_delivery_gate_configs(domain, delivery_gate_configs)

    # -- Load KB entries --------------------------------------------------
    kb_store = KBStore()
    entries = kb_store.list_entries(domain, limit=5000)

    # --- Content-preference tier filtering (B-001) ---------------------------
    content_preference: str = _resolve_content_preference(user_id)
    if content_preference != "both":
        filtered_entries = _filter_entries_by_content_preference(entries, content_preference)
        if len(filtered_entries) != len(entries):
            logger.info(
                "Excluded %d entries from tutorial for domain '%s' due to content_preference='%s'",
                len(entries) - len(filtered_entries),
                domain,
                content_preference,
            )
        entries = filtered_entries

    # --- Test/empty entry filtering (issue #298 — layer 1) -------------------
    entries = _filter_product_entries(entries)

    # --- Per-domain exclude_keywords filter (issue #319) ---------------------
    # Cross-domain noise guard: drop entries matching their own domain's
    # exclude_keywords blacklist BEFORE LLM synthesis / KB-derived sections.
    entries = _filter_entries_by_domain_exclusions(entries, domain)

    # --- Language-learning wiring (backup #59/#61/#63) -----------------------
    # Language-learning domains (default_language set) get: (1) a topic-level
    # guard dropping entries that teach a language OTHER than the domain's
    # target (#63, e.g. a Spanish grammar post in english-learning — the
    # language filter cannot catch English-written posts about another
    # language), and (2) a language-teaching tutorial prompt instead of the
    # generic news-structure prompt (#59/#61).
    lang_learning = _is_lang_learning_domain(domain)
    target_language = (
        (
            _resolve_effective_language(language="", domain=domain)
            or _seed_domain_default_language(domain)
        )
        if lang_learning
        else ""
    )
    # Issue #162: the learner's gloss language for Vocabulary translations
    # (defaults to English when the domain config does not set gloss_language).
    gloss_language = _resolve_gloss_language(domain) if lang_learning else ""
    if lang_learning and target_language:
        entries = _filter_foreign_language_teaching_entries(entries, target_language)

    # --- Staleness filter (backup #60) ---------------------------------------
    # Teaching-layer products must never silently regenerate from an old
    # corpus (e.g. 2024 Corriere after a source swap to ANSA).  Mirror the
    # digest freshness filter; all-stale raises StaleSourceError (plain path)
    # or blocks delivery (DeliveryOutput path) instead of shipping a stale
    # empty-shell product.
    prior_count = len(entries)
    entries = _filter_stale_entries(
        entries, domain, include_stale=include_stale, product="tutorial"
    )
    if not include_stale and prior_count > 0 and not entries:
        stale_msg = (
            f"All {prior_count} candidate entries for domain '{domain}' are stale. "
            f"Refusing to generate an empty-shell tutorial from old corpus. "
            f"Re-run collection to refresh the source, or pass include_stale=true."
        )
        if delivery_gate_configs is not None:
            return DeliveryOutput(
                output="",
                gate_results={},
                delivery_blocked=True,
                delivery_format=format,
                warnings=[f"STALE_SOURCE: {stale_msg}"],
            )
        raise StaleSourceError(stale_msg)

    if not entries:
        if format == "agent":
            return json.dumps(
                {
                    "@context": _JSONLD_TUTORIAL["@context"],
                    "@type": _JSONLD_TUTORIAL["@type"],
                    "error": {
                        "code": "EMPTY_CONTENT",
                        "message": (
                            f"No curated items are available for domain '{domain}' yet. "
                            "Cannot generate an agent-format tutorial."
                        ),
                    },
                    "entries": [],
                },
                indent=2,
                ensure_ascii=False,
            )
        empty_md = (
            f"# {_domain_display_name(domain)} — Tutorial\n\n"
            f"This edition has no curated items yet. Check back after the next collection run."
        )
        if delivery_gate_configs is not None:
            result = _apply_delivery_gates(
                rendered_output=empty_md,
                output_format=format,
                entries=[],
                context={},
                product_type="tutorial",
                delivery_gate_configs=delivery_gate_configs,
                llm_config=llm_config,
            )
            return _apply_min_content_guard(result, [], "tutorial")
        return empty_md

    # -- Build LLM prompt with audience adaptation ------------------------
    audience_desc = _AUDIENCE_DESCRIPTIONS.get(target_audience, "general audience")
    # Cap KB entries sent to the LLM: DeepSeek-V4-Flash is a reasoning
    # model — a long prompt burns max_tokens on reasoning_content and
    # emits empty/truncated content (issue #178 backups). Thick domains
    # (e.g. medical-research: 602 files) feed every filtered entry
    # unbounded, blowing the prompt out of the safe window and timing out
    # at 0B (backup issue #103). 10 representative entries (title +
    # summary) keep the prompt small while still grounding the tutorial in
    # domain facts.
    entry_summaries = "\n".join(
        f"- [{e.get('entry_id', '?')}] {e.get('title', '?')}: "
        f"{e.get('summary', '(no summary)')}"
        + (f" (Source: {e['source_url']})" if e.get("source_url") else "")
        for e in entries[:10]  # cap entries sent to LLM (#178 protocol, backup #103)
    )

    if format == "agent":
        prompt = _build_tutorial_json_prompt(
            target_audience,
            audience_desc,
            entry_summaries,
            custom_instructions,
            lang_learning=lang_learning,
            target_language=target_language,
            gloss_language=gloss_language,
        )
    else:
        prompt = _build_tutorial_markdown_prompt(
            target_audience,
            audience_desc,
            entry_summaries,
            custom_instructions,
            lang_learning=lang_learning,
            target_language=target_language,
            gloss_language=gloss_language,
        )

    llm_result = _call_llm_for_tutorial(prompt)

    # -- Deterministic completeness (markdown path) --------------------------
    # DeepSeek-V4-Flash does not reliably emit the tutorial schema as
    # parseable JSON or markdown with a stable shape.  Ensure a domain that
    # HAS entries never renders the all-empty template: replace an unusable
    # LLM result entirely and fill any still-missing sections from KB entries.
    if format in ("markdown", "agent"):
        # Deterministic completeness: DeepSeek-V4-Flash does not reliably
        # emit the tutorial schema as parseable JSON/markdown.  A domain
        # that HAS entries must never render an empty tutorial — for
        # markdown AND agent (agent consumes the same KB-derived content;
        # without this, an empty LLM result yields slides/steps=[] shells,
        # e.g. 26 empty tutorial-agent artifacts in the 2026-08-11 fill
        # run).
        if not _tutorial_has_content(llm_result):
            logger.warning(
                "Tutorial LLM output unusable for domain '%s' (missing "
                "objectives/content); falling back to KB-derived tutorial",
                domain,
            )
        llm_result = _ensure_tutorial_complete(
            llm_result,
            domain,
            entries,
            target_audience,
            lang_learning=lang_learning,
            target_language=target_language,
            gloss_language=gloss_language,
        )

    # -- Build template context -------------------------------------------
    # Issue #138: day-granularity timestamp (no microseconds).
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _coerce_exercise(item: Any) -> dict[str, str]:
        """Normalize one exercise entry to the ``{title, description}`` shape.

        LLM results occasionally carry plain strings (or scalars) instead of
        objects; rendering those through ``{{ exercise.title }}`` leaks
        Jinja's method-object repr into the product (backup-repo #22-#37
        matrix `_no_placeholder` P0 on gaming tutorial).
        """
        if isinstance(item, dict):
            return {
                "title": str(item.get("title") or item.get("question") or ""),
                "description": str(item.get("description") or ""),
            }
        return {"title": str(item), "description": ""}

    exercises_raw = llm_result.get("exercises", [])
    if isinstance(exercises_raw, list):
        exercises = [_coerce_exercise(item) for item in exercises_raw]
    else:
        exercises = []

    # P0-2: KB references for the tutorial template's ``## Sources`` section
    # (report-context item shape, deduplicated in entry order, no LLM call).
    kb_references: list[dict[str, Any]] = []
    _seen_urls: set[str] = set()
    for entry in entries:
        url = str(entry.get("source_url") or "").strip()
        if not url or url in _seen_urls:
            continue
        _seen_urls.add(url)
        kb_references.append(
            {
                "title": entry.get("title") or "",
                "source_url": url,
                "source_type": entry.get("source_type") or "",
                "source_platform": entry.get("source_platform") or "",
                "source_label": entry.get("source_label") or "",
                "domain": entry.get("domain") or domain,
            }
        )

    context = {
        "title": llm_result.get("title", f"{_domain_display_name(domain)} — Tutorial"),
        "domain": domain,
        "target_audience": target_audience,
        "collection_id": collection_id or "",
        "duration": llm_result.get("duration", "TBD"),
        "prerequisites": llm_result.get("prerequisites", "None"),
        "objectives": llm_result.get("objectives", []),
        "content": llm_result.get("content", []),
        "exercises": exercises,
        "summary": llm_result.get("summary", ""),
        "further_reading": llm_result.get("further_reading", []),
        "references": kb_references,
        "generated_at": generated_at,
        "vocabulary": llm_result.get("vocabulary", []),
        "grammar": llm_result.get("grammar", []),
    }

    # -- Agent-native JSON-LD format ----------------------------------------
    if format == "agent":
        rendered_agent = _render_tutorial_agent_json(
            llm_result, domain, target_audience, generated_at, entries
        )
        _fire_agent_notification("new_tutorial", rendered_agent, product_id=f"{domain}-tutorial")
        return rendered_agent

    # -- Render via Jinja2 template ---------------------------------------
    rendered_tutorial = _render_tutorial_template(context)

    # --- Delivery gates (D1-D3) ---------------------------------------------
    if delivery_gate_configs is not None:
        result = _apply_delivery_gates(
            rendered_output=rendered_tutorial,
            output_format=format,
            entries=entries,
            context=context,
            product_type="tutorial",
            delivery_gate_configs=delivery_gate_configs,
            llm_config=llm_config,
        )
        result = _apply_min_content_guard(result, entries, "tutorial")
        if user_id:
            _try_notify_content_ready(
                user_id=user_id,
                product_type="tutorial",
                title=f"{_domain_display_name(domain)} — Tutorial",
            )
        _fire_agent_notification(
            "new_tutorial",
            result.output if isinstance(result, DeliveryOutput) else rendered_tutorial,
            product_id=f"{domain}-tutorial",
        )
        return result

    _fire_agent_notification("new_tutorial", rendered_tutorial, product_id=f"{domain}-tutorial")
    return rendered_tutorial


def _render_tutorial_agent_json(
    llm_result: dict[str, Any],
    domain: str,
    target_audience: str,
    generated_at: str,
    entries: list[dict[str, Any]],
) -> str:
    """Render tutorial data as agent-native JSON-LD (``@type: KnowledgeTutorial``)."""
    # Derive source entries from KB
    from autoinfo.output import _JSONLD_TUTORIAL, _domain_display_name  # noqa: PLC0415

    source_entries: list[dict[str, Any]] = []
    for e in entries[:50]:
        source_entries.append(
            {
                "entry_id": e.get("entry_id", ""),
                "title": e.get("title", ""),
                "source_url": e.get("source_url", ""),
                "source_platform": e.get("source_platform", ""),
            }
        )

    # Build steps from content sections
    steps: list[dict[str, Any]] = []
    for i, section in enumerate(llm_result.get("content", []), 1):
        steps.append(
            {
                "step": i,
                "heading": section.get("heading", ""),
                "body": section.get("body", ""),
                "code_example": section.get("code_example"),
                "code_language": section.get("code_language"),
                "key_takeaway": section.get("key_takeaway"),
            }
        )

    # Build exercises
    exercises: list[dict[str, Any]] = []
    for ex in llm_result.get("exercises", []):
        exercises.append(
            {
                "title": ex.get("title", ""),
                "description": ex.get("description", ""),
                "hint": ex.get("hint"),
                "solution": ex.get("solution"),
            }
        )

    output: dict[str, Any] = {
        **_JSONLD_TUTORIAL,
        "uuid": str(uuid.uuid4()),
        "title": llm_result.get("title", f"{_domain_display_name(domain)} — Tutorial"),
        "domain": domain,
        "target_audience": target_audience,
        "duration": llm_result.get("duration", "TBD"),
        "prerequisites": llm_result.get("prerequisites", ""),
        "objectives": llm_result.get("objectives", []),
        "steps": steps,
        "exercises": exercises,
        "summary": llm_result.get("summary", ""),
        "further_reading": llm_result.get("further_reading", []),
        "source_entries": source_entries,
        "generated_at": generated_at,
        "metadata": {
            "entry_count": len(entries),
            "step_count": len(steps),
            "exercise_count": len(exercises),
        },
    }
    return json.dumps(output, indent=2, ensure_ascii=False, default=str)


def _call_llm_for_tutorial(prompt: str) -> dict[str, Any]:
    """Call LiteLLM to generate structured tutorial content.

    Uses the same pattern as ``_call_llm_for_digest``.
    """
    from autoinfo.output import (  # noqa: PLC0415
        Config,
        _parse_json_response,
        _parse_tutorial_markdown,
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
                    "content": get_prompt("tutorial_system"),
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
        logger.error("Tutorial generation failed: %s", exc)
        return {}
    content: str = response.choices[0].message.content or ""
    if not content:
        return {}
    parsed = _parse_json_response(content)
    if parsed:
        return parsed
    return _parse_tutorial_markdown(content)


def _build_tutorial_json_prompt(
    target_audience: str,
    audience_desc: str,
    entry_summaries: str,
    custom_instructions: str,
    *,
    lang_learning: bool = False,
    target_language: str = "",
    gloss_language: str = "",
) -> str:
    """Build the structured-JSON tutorial prompt (agent-native format path).

    For language-learning domains (*lang_learning* + *target_language*),
    the schema gains ``vocabulary`` and ``grammar`` arrays and the content is
    required to be written in the target language (backup #59/#61).  A
    no-fabricated-causal-attribution constraint is always appended (#62).
    """
    from autoinfo.output import URL_VERBATIM_CONSTRAINT, _lang_display_name  # noqa: PLC0415

    prompt = (
        f"You are a tutorial designer creating content for a {target_audience} "
        f"audience ({audience_desc}). "
        "Given the following knowledge base entries, structure them into a "
        "coherent learning path. "
        "Return a JSON object with the following fields:\n"
        '  - "title": tutorial title (string)\n'
        '  - "duration": estimated reading/completion time (string, e.g. "45 minutes")\n'
        '  - "prerequisites": comma-separated prerequisites (string)\n'
        '  - "objectives": array of 3-5 learning objective strings, each a '
        "learning-verb goal (Understand / Analyze / Apply / Evaluate), NEVER "
        "a verbatim copy of a KB entry title\n"
        '  - "content": array of section objects, each with:\n'
        '      - "heading": section heading\n'
        '      - "body": 2-4 paragraph section content\n'
        '      - "code_example": optional code/example snippet (string or null)\n'
        '      - "code_language": language for the code snippet (string or null)\n'
        '      - "key_takeaway": one-line takeaway (string or null)\n'
        '  - "exercises": array of exercise objects, each with:\n'
        '      - "title": exercise title\n'
        '      - "description": exercise description\n'
        '      - "hint": optional hint (string or null)\n'
        '      - "solution": optional solution (string or null)\n'
        '  - "summary": 2-3 sentence summary of the tutorial\n'
        '  - "further_reading": array of reference strings\n\n'
        f"KB Entries:\n{entry_summaries}\n\n"
        'In every "content" section body, follow each key claim with an '
        'inline citation to its source entry, e.g. "(Source: <source_url>)". '
        "Only cite URLs present in the KB Entries list. " + URL_VERBATIM_CONSTRAINT + "\n"
        "Return all fields in a single JSON object. Adapt depth, terminology, "
        f"and examples specifically for a {target_audience} audience."
    )
    if lang_learning and target_language:
        lang_label = _lang_display_name(target_language)
        # Issue #162: gloss translations in the learner's language.
        gloss_label = _lang_display_name(gloss_language) if gloss_language else "English"
        prompt += (
            f"\n\nThis is a LANGUAGE-LEARNING tutorial for {lang_label}. "
            "Write the tutorial as a language course, not a news summary:\n"
            '- "objectives" MUST be language-ability goals for learners of '
            f'{lang_label} (e.g. "Understand how to report on current '
            'events in the target language"), NOT copies of the KB entry titles.\n'
            f'- "content" sections MUST be written IN {lang_label} '
            "(target-language prose adapted to a graded learner level), not "
            "an English retelling.\n"
            '- add two extra keys to the JSON: "vocabulary" (array of objects '
            'with "word" (in target language), "pos" (part of speech), '
            f'"translation" (MUST be in {gloss_label}, never another language), '
            '"example" (a sentence in the target language)) '
            'and "grammar" (array of objects with "point" (grammar rule name), '
            '"explanation", "example" (target-language example)).\n'
            f'- "exercises" MUST be {lang_label} exercises (fill-in-the-blank, '
            f"translation, sentence construction in {lang_label}), not "
            "English comprehension questions. Provide EXACTLY 4 exercises; "
            "each has a short title and a full question body (never embed the "
            "answer in the question).\n"
        )
    prompt += (
        "\nDo NOT add causal attributions, motivations, or explanations (e.g. "
        "'due to COVID-19 concerns', 'likely because of') that the source "
        "entries do not explicitly state. Only restate causes actually present "
        "in the source material."
    )
    if custom_instructions:
        prompt += f"\n\nAdditional instructions: {custom_instructions}"
    return prompt


def _build_tutorial_markdown_prompt(
    target_audience: str,
    audience_desc: str,
    entry_summaries: str,
    custom_instructions: str,
    *,
    lang_learning: bool = False,
    target_language: str = "",
    gloss_language: str = "",
) -> str:
    """Build the flat-markdown tutorial prompt (robust markdown render path).

    Plain markdown with fixed heading markers is far more reliably emitted by
    the default model than the nested tutorial JSON schema, and the response is
    parsed by heading instead of ``json.loads``.

    For language-learning domains (*lang_learning* + *target_language*), the
    required structure gains ``## Vocabulary`` and ``## Grammar`` sections and
    the body/exercises must be written in the target language (backup #59/#61).
    A no-fabricated-causal-attribution constraint is always appended (#62).
    """
    from autoinfo.output import URL_VERBATIM_CONSTRAINT, _lang_display_name  # noqa: PLC0415

    prompt = (
        f"You are a tutorial designer creating content for a {target_audience} "
        f"audience ({audience_desc}). "
        "Given the following knowledge base entries, structure them into a "
        "coherent learning path. "
        "Return plain Markdown with this exact structure:\n\n"
        "# <tutorial title>\n"
        "Duration: <estimated reading/completion time, e.g. '45 minutes'>\n"
        "Prerequisites: <comma-separated prerequisites or 'None'>\n\n"
        "## Learning Objectives\n"
        "- <objective 1>\n"
        "- <objective 2>\n"
        "- <objective 3>\n\n"
        "## Content\n"
        "### <section heading 1>\n"
        "<2-4 paragraphs of section content>\n"
        "### <section heading 2>\n"
        "<2-4 paragraphs of section content>\n\n"
        "## Exercises\n"
        "- <exercise 1>\n"
        "- <exercise 2>\n\n"
        "## Summary\n"
        "<2-3 sentence summary>\n\n"
        "## Further Reading\n"
        "- <reference 1>\n"
        "- <reference 2>\n\n"
        "In every content paragraph, follow each key claim with an inline "
        'citation to its source entry, e.g. "(Source: <source_url>)". Only '
        "cite URLs present in the KB Entries list. " + URL_VERBATIM_CONSTRAINT + "\n\n"
        "Use exactly the heading names above. Do NOT wrap your answer in a "
        "code fence or emit JSON.\n\n"
        f"KB Entries:\n{entry_summaries}\n\n"
        "Adapt depth, terminology, and examples specifically for a "
        f"{target_audience} audience."
    )
    if lang_learning and target_language:
        lang_label = _lang_display_name(target_language)
        # Issue #162: vocabulary glosses must be in the learner's gloss
        # language (default English) — never the model's arbitrary pick
        # (observed: Korean glosses in an english-learning tutorial).
        gloss_label = _lang_display_name(gloss_language) if gloss_language else "English"
        prompt += (
            f"\n\nThis is a LANGUAGE-LEARNING tutorial for {lang_label}. "
            "Write the tutorial as a language course, not a news summary:\n"
            f"- Learning Objectives MUST be language-ability goals for learners "
            f'of {lang_label} (e.g. "Understand how to report on current '
            'events in the target language"), NOT copies of the KB article titles.\n'
            f"- The tutorial body MUST be written in the target language "
            f"({lang_label}); target-language prose adapted to a graded "
            "learner level, not an English retelling. Only technical terms may "
            "stay in the source language.\n"
            f"- Add a '## Vocabulary' section listing 6-10 target-language words "
            f"from the entries, each bullet: '<word> — <part of speech> — "
            f"<translation in {gloss_label}> — <example sentence in the target "
            f"language>'.  The translation MUST be written in {gloss_label}, "
            "never in another language.\n"
            "- Add a '## Grammar' section listing 2-3 grammar points relevant "
            "to the content, each bullet: '<grammar point> — <rule> — "
            "<example in the target language>'.\n"
            f"- Exercises MUST be written in the target language "
            f"(fill-in-the-blank, translation, sentence construction in "
            f"{lang_label}), not English comprehension questions.\n"
            # Issue #163: constrain the exercise format and count so the
            # model never emits bare '### Exercise N:' titles with no body,
            # inline answers, or an unbounded list that truncates the tail.
            "- Write EXACTLY 4 exercises. Each exercise is: a short "
            "'### Exercise N:' title (number + one-word type, e.g. "
            "'### Exercise 1: Fill-in-the-blank') followed by the FULL "
            "question text on its own line (fill-in-the-blank uses ______ "
            "for the gap; rewriting gives the original sentence). Do NOT "
            "embed the answer in the question.\n"
            "- After all 4 exercises, add a '#### Answer Key' section "
            "listing the answer for each exercise by number. Never put an "
            "answer inside a question.\n"
        )
    prompt += (
        "\nDo NOT add causal attributions, motivations, or explanations (e.g. "
        "'due to COVID-19 concerns', 'likely because of') that the source "
        "entries do not explicitly state. Only restate causes actually present "
        "in the source material."
    )
    if custom_instructions:
        prompt += f"\n\nAdditional instructions: {custom_instructions}"
    return prompt


def _parse_tutorial_markdown(content: str) -> dict[str, Any]:
    """Parse a markdown tutorial response into the tutorial context schema.

    Handles the structure requested by ``_build_tutorial_markdown_prompt``:
    ``# title``, optional ``Duration:`` / ``Prerequisites:`` lines,
    ``## Learning Objectives`` bullets, ``## Content`` with ``### <heading>``
    subsections, ``## Exercises`` bullets or ``### Exercise N:`` headings,
    ``## Summary`` paragraph and ``## Further Reading`` bullets.  Returns
    ``{}`` when *content* is empty.
    """
    if not content:
        return {}
    result: dict[str, Any] = {
        "title": "",
        "duration": "",
        "prerequisites": "",
        "objectives": [],
        "content": [],
        "exercises": [],
        "summary": "",
        "further_reading": [],
        "vocabulary": [],
        "grammar": [],
    }
    current_section = ""
    content_heading = ""
    content_body: list[str] = []
    exercise_title = ""
    exercise_body: list[str] = []

    def flush_content() -> None:
        nonlocal content_heading, content_body
        if content_heading:
            result["content"].append(
                {
                    "heading": content_heading,
                    "body": "\n\n".join(line.strip() for line in content_body).strip(),
                }
            )
            content_heading = ""
            content_body = []

    def flush_exercise() -> None:
        nonlocal exercise_title, exercise_body
        if exercise_title:
            result["exercises"].append(
                {
                    "title": exercise_title,
                    "description": "\n\n".join(line.strip() for line in exercise_body).strip(),
                }
            )
            exercise_title = ""
            exercise_body = []

    def is_bullet(text: str) -> bool:
        return bool(re.match(r"^(?:[-*]|\d+[.)])\s+\S", text))

    def bullet_text(text: str) -> str:
        return re.sub(r"^(?:[-*]|\d+[.)])\s+", "", text).strip()

    for raw in content.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            result["title"] = stripped.lstrip("#").strip()
            continue
        if not current_section and (
            stripped.lower().startswith("duration:")
            or stripped.lower().startswith("prerequisites:")
        ):
            key, _, value = stripped.partition(":")
            result[key.strip().lower()] = value.strip()
            continue
        if stripped.startswith("## "):
            flush_content()
            flush_exercise()
            current_section = stripped.lstrip("#").strip()
            continue
        if current_section in ("Learning Objectives", "Learning Goals"):
            if is_bullet(stripped):
                item = bullet_text(stripped)
                if item:
                    result["objectives"].append(item)
            continue
        if current_section == "Content":
            if stripped.startswith("### "):
                flush_content()
                content_heading = stripped.lstrip("#").strip()
                content_body = []
            elif content_heading and stripped:
                content_body.append(stripped)
            continue
        if current_section in ("Exercises", "Practice", "Practice Exercises"):
            if stripped.startswith("### "):
                flush_exercise()
                heading = stripped.lstrip("#").strip()
                exercise_title = (
                    re.sub(
                        r"^Exercise\s*(\d+)?\s*[:.)-]?\s*",
                        "",
                        heading,
                        flags=re.IGNORECASE,
                    ).strip()
                    or heading
                )
                exercise_body = []
            elif is_bullet(stripped):
                flush_exercise()
                item = bullet_text(stripped)
                if item:
                    result["exercises"].append({"title": item, "description": ""})
            elif exercise_title and stripped:
                exercise_body.append(stripped)
            continue
        if current_section in ("Summary", "Conclusion", "Wrap-Up"):
            if stripped:
                result["summary"] = (result["summary"] + " " + stripped).strip()
            continue
        if current_section in ("Further Reading", "References", "Resources"):
            if is_bullet(stripped):
                item = bullet_text(stripped)
                if item:
                    result["further_reading"].append(item)
            elif stripped and not line.startswith(("---", "***")):
                result["further_reading"].append(stripped)
            continue
        if current_section in ("Vocabulary", "Key Vocabulary", "Word List"):
            if is_bullet(stripped):
                item = bullet_text(stripped)
                if item:
                    result["vocabulary"].append(item)
            continue
        if current_section in ("Grammar", "Grammar Points", "Grammar Notes"):
            if is_bullet(stripped):
                item = bullet_text(stripped)
                if item:
                    result["grammar"].append(item)
            continue
    flush_content()
    flush_exercise()
    return result


def _tutorial_has_content(result: dict[str, Any]) -> bool:
    """True when a tutorial LLM result carries real objectives, content and
    a summary — a shell missing any of the three is not a usable tutorial."""
    return (
        bool(result.get("objectives"))
        and bool(result.get("content"))
        and bool((result.get("summary") or "").strip())
    )


def _entry_derived_sections(
    entries: list[dict[str, Any]],
    *,
    lang_learning: bool = False,
    target_language: str = "",
) -> tuple[list[str], list[dict[str, str]], list[dict[str, str]], list[str]]:
    """Derive objectives/content/exercises/further-reading from KB entries.

    For language-learning domains (*lang_learning* + *target_language*), the
    KB-derived fallback exercises become target-language writing practice
    instead of English "key finding" questions (backup #59).
    """
    objectives: list[str] = []
    content: list[dict[str, str]] = []
    exercises: list[dict[str, str]] = []
    further_reading: list[str] = []
    for index, entry in enumerate(entries):
        # Issue #85: never surface the internal "Entry N" numbering as a
        # user-facing heading when a title is missing — use a neutral label.
        title = entry.get("title") or "Untitled entry"
        summary = entry.get("summary") or "(no summary available)"
        if len(objectives) < 5:
            # Issue #92: learning-verb phrasing — never a verbatim copy of
            # the KB entry title (a title is not a learning objective).
            objectives.append(f"Understand the key findings in '{title}'")
        body = summary
        url = entry.get("source_url")
        if url:
            body += f" (Source: {url})"
        content.append({"heading": title, "body": body})
        lang_label = target_language or "the target language"
        exercises.append(
            {
                "title": f"Write a {len(body.split()):d}-word summary",
                "description": (
                    f"Read '{title}' and write a short summary in {lang_label}. "
                    "Use at least 3 words or phrases from the article."
                ),
            }
            if lang_learning
            else {
                "title": f"What is the key finding in '{title}'?",
                "description": (
                    f"Summarize the main finding or conclusion of the entry "
                    f"'{title}' in one or two sentences."
                ),
            }
        )
        if url and url not in further_reading:
            further_reading.append(url)
    return objectives[:5], content, exercises, further_reading[:20]


def _validated_exercises(
    llm_exercises: list[Any], fallback: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Return the LLM exercises minus empty-bodied shells, else the fallback.

    Issue #163/#164: the flat-markdown parse can produce ``{title, ''}``
    entries (the model emitted a bare ``### Exercise N:`` heading with no
    body).  Drop entries whose description is empty/whitespace-only; when
    fewer than 2 real exercises survive, use the deterministic KB-derived
    *fallback* so the tutorial never ships a hollow exercise section.
    """
    if not llm_exercises:
        return list(fallback)
    valid: list[dict[str, str]] = []
    for item in llm_exercises:
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("question") or "").strip()
            desc = str(item.get("description") or "").strip()
            if title and desc:
                valid.append({"title": title, "description": desc})
        elif isinstance(item, str) and item.strip():
            valid.append({"title": item.strip(), "description": ""})
    if len(valid) >= 2:
        return valid
    return list(fallback)


def _ensure_tutorial_complete(
    llm_result: dict[str, Any],
    domain: str,
    entries: list[dict[str, Any]],
    target_audience: str,
    *,
    lang_learning: bool = False,
    target_language: str = "",
    gloss_language: str = "",
) -> dict[str, Any]:
    """Guarantee the markdown tutorial never renders the all-empty template.

    Keeps every usable field from *llm_result* (title, duration, objectives,
    content, …) and fills any missing or empty section from the KB entries,
    so a domain that HAS entries always produces a complete tutorial.
    """
    from autoinfo.output import (  # noqa: PLC0415
        _domain_display_name,
        _entry_derived_sections,
        _validated_exercises,
    )

    objectives, content, exercises, further_reading = _entry_derived_sections(
        entries,
        lang_learning=lang_learning,
        target_language=target_language,
    )
    title = llm_result.get("title") or ""
    # Issue #92: an LLM that returns a digest/report-style title ("Weekly
    # Digest — <domain>") must not mislabel a Tutorial product — override
    # with the Tutorial semantic title.
    if not title or any(
        marker in title.lower() for marker in ("weekly digest", "digest —", "report —")
    ):
        title = f"{_domain_display_name(domain)} — Tutorial"

    # Issue #92: an LLM that copies KB entry titles verbatim as objectives
    # ("Learning Objectives 照抄文章标题") is not teaching — replace the
    # objectives with the derived learning-verb phrasing when >= 2 of them
    # are bare entry-title copies.
    llm_objectives = llm_result.get("objectives") or []
    entry_titles = {str(e.get("title") or "").strip() for e in entries}
    title_copies = sum(1 for o in llm_objectives if str(o).strip() in entry_titles)
    if title_copies >= 2:
        llm_objectives = objectives

    # Issue #92: language-learning domains need a real teaching structure.
    # When the LLM returns no vocabulary/grammar, derive a deterministic
    # vocabulary list from the target-language summaries (distinctive >=4
    # char words, capped) and a grammar point from the first summary's
    # sentence structure — so a lang tutorial is never a bare article dump.
    llm_vocabulary = llm_result.get("vocabulary") or []
    llm_grammar = llm_result.get("grammar") or []
    if lang_learning and not llm_vocabulary:
        seen: set[str] = set()
        for e in entries:
            for token in re.findall(r"[A-Za-zÀ-ÿ'’]{4,}", str(e.get("summary") or "")):
                low = token.lower()
                if low in seen:
                    continue
                seen.add(low)
                llm_vocabulary.append(f"{token} — key vocabulary from the article")
                if len(llm_vocabulary) >= 5:
                    break
            if len(llm_vocabulary) >= 5:
                break
    if lang_learning and not llm_grammar:
        first_summary = next((str(e.get("summary") or "") for e in entries if e.get("summary")), "")
        if first_summary:
            llm_grammar.append(
                f'Sentence structure — follow the clause order in "{first_summary.strip()[:60]}"'
            )
    # Issue #92: treat placeholder duration/prerequisites ("TBD", "None",
    # "0 minutes") as empty so a shell LLM result is filled deterministically.
    raw_duration = str(llm_result.get("duration") or "").strip()
    if raw_duration.lower() in ("tbd", "none", "0 minutes", "", "n/a"):
        duration = f"{len(entries)} minutes"
    else:
        duration = raw_duration
    raw_prereq = str(llm_result.get("prerequisites") or "").strip()
    if raw_prereq.lower() in ("tbd", "none", "", "n/a"):
        prerequisites = "None (no prior experience required)"
    else:
        prerequisites = raw_prereq
    return {
        "title": title,
        "duration": duration,
        "prerequisites": prerequisites,
        "objectives": llm_objectives or objectives,
        "content": llm_result.get("content") or content,
        # Issue #163/#164: the flat-markdown parse can yield "### Exercise N:"
        # shells whose description is empty (the model emitted only a title —
        # observed with ark-code-latest: 21 titles / 1 non-empty, 13 titles /
        # 5 non-empty).  Drop empty-bodied exercises; if fewer than 2 real
        # exercises survive, fall back to the deterministic KB-derived set so
        # the tutorial never ships a hollow exercise section.
        "exercises": _validated_exercises(llm_result.get("exercises") or [], exercises),
        "summary": llm_result.get("summary")
        or (
            f"This tutorial walks through {len(entries)} knowledge base "
            f"entries in the {domain} domain, covering the key findings "
            f"for a {target_audience} audience."
        ),
        "further_reading": llm_result.get("further_reading") or further_reading,
        "vocabulary": llm_vocabulary,
        "grammar": llm_grammar,
    }


def _render_tutorial_template(context: dict[str, Any]) -> str:
    """Render the tutorial data through ``tutorial.md.j2``."""
    from autoinfo.output import _get_jinja_env  # noqa: PLC0415

    env = _get_jinja_env()
    template = env.get_template("tutorial.md.j2")
    return template.render(**context)
