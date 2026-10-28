"""Output generation — digests, reports, and KB export.

Provides the ``export_kb`` function for exporting knowledge base data
in Markdown (tar.gz), JSON, or SQLite format.

Usage::

    from autoinfo.output import export_kb

    # Export a single domain as JSON
    result = export_kb(domain="medical-research", format="json")

    # Export the entire KB as Markdown tar.gz
    result = export_kb(format="markdown")
"""

from __future__ import annotations

import base64
import html
import json
import logging
import re
import time
import uuid
from datetime import date, timedelta
from datetime import datetime as datetime
from datetime import timezone as timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Final, cast

from autoinfo.output.audience import _AUDIENCE_DESCRIPTIONS as _AUDIENCE_DESCRIPTIONS
from autoinfo.output.audience import _REPORT_AUDIENCE_DESCRIPTIONS as _REPORT_AUDIENCE_DESCRIPTIONS
from autoinfo.output.audience import _REPORT_AUDIENCE_PROMPTS as _REPORT_AUDIENCE_PROMPTS
from autoinfo.output.audience import _VALID_AUDIENCES as _VALID_AUDIENCES
from autoinfo.output.audience import _VALID_REPORT_AUDIENCES as _VALID_REPORT_AUDIENCES
from autoinfo.output.audience import _normalize_report_audience as _normalize_report_audience
from autoinfo.output.audio import (
    DEFAULT_LOCAL_TTS_VOICE as DEFAULT_LOCAL_TTS_VOICE,
)
from autoinfo.output.audio import (
    DEFAULT_TTS_VOICE as DEFAULT_TTS_VOICE,
)
from autoinfo.output.audio import (
    _get_tts_engine_from_config as _get_tts_engine_from_config,
)
from autoinfo.output.audio import (
    _render_audio as _render_audio,
)
from autoinfo.output.audio import (
    _render_audio_edge_tts as _render_audio_edge_tts,
)
from autoinfo.output.audio import (
    _render_audio_openai as _render_audio_openai,
)
from autoinfo.output.audio import (
    _render_audio_whisper as _render_audio_whisper,
)
from autoinfo.output.audio import (
    _render_video_scaffold as _render_video_scaffold,
)
from autoinfo.output.audio import (
    _run_coro_in_new_thread as _run_coro_in_new_thread,
)
from autoinfo.output.audio import (
    _strip_markdown as _strip_markdown,
)
from autoinfo.output.contracts import _DELIVERY_GATES_BYPASS as _DELIVERY_GATES_BYPASS
from autoinfo.output.contracts import _JSONLD_BASE_EXPORT as _JSONLD_BASE_EXPORT
from autoinfo.output.contracts import _JSONLD_DIGEST as _JSONLD_DIGEST
from autoinfo.output.contracts import _JSONLD_PRESENTATION as _JSONLD_PRESENTATION
from autoinfo.output.contracts import _JSONLD_TUTORIAL as _JSONLD_TUTORIAL
from autoinfo.output.contracts import _PRODUCT_ANALYSIS_FIELDS as _PRODUCT_ANALYSIS_FIELDS
from autoinfo.output.contracts import DeliveryOutput as DeliveryOutput
from autoinfo.output.contracts import ReportData as ReportData
from autoinfo.output.contracts import ReportSection as ReportSection
from autoinfo.output.contracts import StaleSourceError as StaleSourceError
from autoinfo.output.contracts import _DeliveryGatesBypass as _DeliveryGatesBypass
from autoinfo.output.gates import _MIN_PRODUCT_CONTENT_CHARS as _MIN_PRODUCT_CONTENT_CHARS
from autoinfo.output.gates import _MIN_PRODUCT_HEADINGS as _MIN_PRODUCT_HEADINGS
from autoinfo.output.gates import _MIN_SUBSTANTIVE_SUMMARY_CHARS as _MIN_SUBSTANTIVE_SUMMARY_CHARS
from autoinfo.output.gates import _PRODUCT_JUDGE_ENABLED as _PRODUCT_JUDGE_ENABLED
from autoinfo.output.gates import _SYNTHETIC_ENTRY_MARKERS as _SYNTHETIC_ENTRY_MARKERS
from autoinfo.output.gates import _apply_delivery_gates as _apply_delivery_gates
from autoinfo.output.gates import _apply_min_content_guard as _apply_min_content_guard
from autoinfo.output.gates import _build_product_judge_prompt as _build_product_judge_prompt
from autoinfo.output.gates import _escalate_product_judge_prompt as _escalate_product_judge_prompt
from autoinfo.output.gates import _is_substantive_entry as _is_substantive_entry
from autoinfo.output.gates import _llm_key_available as _llm_key_available
from autoinfo.output.gates import _parse_product_judge_verdict as _parse_product_judge_verdict
from autoinfo.output.gates import _product_body_text_len as _product_body_text_len
from autoinfo.output.gates import _product_heading_count as _product_heading_count
from autoinfo.output.gates import _product_judge_enabled as _product_judge_enabled
from autoinfo.output.gates import _resolve_delivery_gate_configs as _resolve_delivery_gate_configs
from autoinfo.output.gates import _run_product_judge as _run_product_judge
from autoinfo.output.gates import _sections_from_rendered_body as _sections_from_rendered_body
from autoinfo.output.grouping import (
    _SOURCE_TYPE_THEME_LABEL as _SOURCE_TYPE_THEME_LABEL,
)
from autoinfo.output.grouping import (
    _apply_grouping_target as _apply_grouping_target,
)
from autoinfo.output.grouping import (
    _deterministic_grouping as _deterministic_grouping,
)
from autoinfo.output.grouping import (
    _deterministic_grouping_kind as _deterministic_grouping_kind,
)
from autoinfo.output.grouping import (
    _ensure_all_entries_grouped as _ensure_all_entries_grouped,
)
from autoinfo.output.grouping import (
    _group_batch_by_theme as _group_batch_by_theme,
)
from autoinfo.output.grouping import (
    _group_by_theme as _group_by_theme,
)
from autoinfo.output.grouping import (
    _grouping_degradation_marker as _grouping_degradation_marker,
)
from autoinfo.output.grouping import (
    _keyword_group_entries as _keyword_group_entries,
)
from autoinfo.output.grouping import (
    _keyword_topic_labels as _keyword_topic_labels,
)
from autoinfo.output.grouping import (
    _llm_group_batch as _llm_group_batch,
)
from autoinfo.output.grouping import (
    _load_keyword_topics as _load_keyword_topics,
)
from autoinfo.output.grouping import (
    _log_grouping_degraded as _log_grouping_degraded,
)
from autoinfo.output.grouping import (
    _match_keyword as _match_keyword,
)
from autoinfo.output.grouping import (
    _merge_theme_groups as _merge_theme_groups,
)
from autoinfo.output.grouping import (
    _normalize_text as _normalize_text,
)
from autoinfo.output.grouping import (
    _normalize_theme_text as _normalize_theme_text,
)

# #582 phase 1: implementations live in focused modules; re-exported here
# so existing `autoinfo.output.<name>` monkeypatch seams keep resolving.
from autoinfo.output.grouping import (
    _reset_grouping_degraded as _reset_grouping_degraded,
)
from autoinfo.output.grouping import (
    _run_grouping_batches as _run_grouping_batches,
)
from autoinfo.output.grouping import (
    _seed_topic_keywords as _seed_topic_keywords,
)
from autoinfo.output.grouping import (
    _single_general_group as _single_general_group,
)
from autoinfo.output.grouping import (
    _source_group_heading as _source_group_heading,
)
from autoinfo.output.presentation import (
    _call_llm_for_presentation as _call_llm_for_presentation,
)
from autoinfo.output.presentation import (
    _fallback_slides_from_entries as _fallback_slides_from_entries,
)
from autoinfo.output.presentation import (
    _render_presentation_agent_json as _render_presentation_agent_json,
)
from autoinfo.output.presentation import (
    _render_presentation_html as _render_presentation_html,
)
from autoinfo.output.presentation import (
    _render_presentation_mkslides as _render_presentation_mkslides,
)
from autoinfo.output.presentation import (
    _render_presentation_template as _render_presentation_template,
)
from autoinfo.output.presentation import (
    _split_summary_sentences as _split_summary_sentences,
)
from autoinfo.output.presentation import (
    _truncate_ellipsis as _truncate_ellipsis,
)
from autoinfo.output.presentation import (
    generate_presentation as generate_presentation,
)
from autoinfo.output.render import (
    _digest_chapters as _digest_chapters,
)
from autoinfo.output.render import (
    _render_agent_json as _render_agent_json,
)
from autoinfo.output.render import (
    _render_digest_html as _render_digest_html,
)
from autoinfo.output.render import (
    _render_empty_report as _render_empty_report,
)
from autoinfo.output.render import (
    _render_empty_report_html as _render_empty_report_html,
)
from autoinfo.output.render import (
    _render_html as _render_html,
)
from autoinfo.output.render import (
    _render_json as _render_json,
)
from autoinfo.output.render import (
    _render_markdown as _render_markdown,
)
from autoinfo.output.render import (
    _render_report_html as _render_report_html,
)
from autoinfo.output.render import (
    _render_report_json as _render_report_json,
)
from autoinfo.output.render import (
    _render_report_template as _render_report_template,
)
from autoinfo.output.render import (
    _report_chapters as _report_chapters,
)
from autoinfo.output.render import (
    is_no_data_product as is_no_data_product,
)
from autoinfo.output.report import (
    _DEDICATED_PRODUCT_PROMPT_MAX_FINDING_CHARS as _DEDICATED_PRODUCT_PROMPT_MAX_FINDING_CHARS,
)
from autoinfo.output.report import (
    _DEDICATED_PRODUCT_PROMPT_MAX_FINDINGS as _DEDICATED_PRODUCT_PROMPT_MAX_FINDINGS,
)
from autoinfo.output.report import (
    _DEDICATED_PRODUCT_PROMPT_MAX_SUMMARY_CHARS as _DEDICATED_PRODUCT_PROMPT_MAX_SUMMARY_CHARS,
)
from autoinfo.output.report import _GLUED_BULLET_SEP as _GLUED_BULLET_SEP
from autoinfo.output.report import _RETRY_BACKOFF_SECONDS as _RETRY_BACKOFF_SECONDS
from autoinfo.output.report import _RETRY_DETAIL_CHAR_BUDGET as _RETRY_DETAIL_CHAR_BUDGET
from autoinfo.output.report import _RETRY_MAX_ATTEMPTS as _RETRY_MAX_ATTEMPTS
from autoinfo.output.report import _RETRY_MAX_DETAIL_ENTRIES as _RETRY_MAX_DETAIL_ENTRIES
from autoinfo.output.report import _RETRY_MAX_ENTRY_SUMMARY_CHARS as _RETRY_MAX_ENTRY_SUMMARY_CHARS
from autoinfo.output.report import _build_product_sections_prompt as _build_product_sections_prompt
from autoinfo.output.report import _build_report_entries_detail as _build_report_entries_detail
from autoinfo.output.report import _build_report_synthesis_prompt as _build_report_synthesis_prompt
from autoinfo.output.report import _call_llm_for_report_synthesis as _call_llm_for_report_synthesis
from autoinfo.output.report import _generate_executive_summary as _generate_executive_summary
from autoinfo.output.report import _llm_json_extract as _llm_json_extract
from autoinfo.output.report import _parse_report_markdown as _parse_report_markdown
from autoinfo.output.report import _report_data_to_dict as _report_data_to_dict
from autoinfo.output.report import (
    _report_product_fields_for_family as _report_product_fields_for_family,
)
from autoinfo.output.report import _split_glued_bullets as _split_glued_bullets
from autoinfo.output.sources import _DEMO_DOMAINS_DIR as _DEMO_DOMAINS_DIR
from autoinfo.output.sources import _GENERIC_PLATFORMS as _GENERIC_PLATFORMS
from autoinfo.output.sources import _MATCHABLE_SOURCE_TYPES as _MATCHABLE_SOURCE_TYPES
from autoinfo.output.sources import _REF_LANG_LEARNING_DOMAINS as _REF_LANG_LEARNING_DOMAINS
from autoinfo.output.sources import _derive_source_label as _derive_source_label
from autoinfo.output.sources import _filter_drifted_entries as _filter_drifted_entries
from autoinfo.output.sources import _host_matches_source as _host_matches_source
from autoinfo.output.sources import _is_lang_learning_domain as _is_lang_learning_domain
from autoinfo.output.sources import _is_source_active_in_config as _is_source_active_in_config
from autoinfo.output.sources import _label_entries as _label_entries
from autoinfo.output.templating import _PRODUCT_H1_WORDS as _PRODUCT_H1_WORDS
from autoinfo.output.templating import FORMAT_TO_VARIANT as FORMAT_TO_VARIANT
from autoinfo.output.templating import PRODUCT_TEMPLATES as PRODUCT_TEMPLATES
from autoinfo.output.templating import TEMPLATE_PATH as TEMPLATE_PATH
from autoinfo.output.templating import ProductTemplate as ProductTemplate
from autoinfo.output.templating import _get_jinja_env as _get_jinja_env
from autoinfo.output.templating import _html_autoescape as _html_autoescape
from autoinfo.output.templating import _jinja_env as _jinja_env
from autoinfo.output.templating import _product_h1_word as _product_h1_word
from autoinfo.output.templating import _resolve_digest_product_type as _resolve_digest_product_type
from autoinfo.output.templating import _resolve_report_product_type as _resolve_report_product_type
from autoinfo.output.templating import list_output_templates as list_output_templates
from autoinfo.output.tutorial import (
    _build_tutorial_json_prompt as _build_tutorial_json_prompt,
)
from autoinfo.output.tutorial import (
    _build_tutorial_markdown_prompt as _build_tutorial_markdown_prompt,
)
from autoinfo.output.tutorial import (
    _call_llm_for_tutorial as _call_llm_for_tutorial,
)
from autoinfo.output.tutorial import (
    _ensure_tutorial_complete as _ensure_tutorial_complete,
)
from autoinfo.output.tutorial import (
    _entry_derived_sections as _entry_derived_sections,
)
from autoinfo.output.tutorial import (
    _parse_tutorial_markdown as _parse_tutorial_markdown,
)
from autoinfo.output.tutorial import (
    _render_tutorial_agent_json as _render_tutorial_agent_json,
)
from autoinfo.output.tutorial import (
    _render_tutorial_template as _render_tutorial_template,
)
from autoinfo.output.tutorial import (
    _tutorial_has_content as _tutorial_has_content,
)
from autoinfo.output.tutorial import (
    _validated_exercises as _validated_exercises,
)
from autoinfo.output.tutorial import (
    generate_tutorial as generate_tutorial,
)

if TYPE_CHECKING:
    from autoinfo.config import SourceConfig  # noqa: F811

from autoinfo.config import Config as Config
from autoinfo.config import get_config_path as get_config_path
from autoinfo.config import load_config as load_config
from autoinfo.grounding import HONEST_HEDGE_RE, grounding_corpus, split_sentences
from autoinfo.kb import KBStore as KBStore
from autoinfo.kb import PromotionRejected
from autoinfo.llm import call_with_fallback as call_with_fallback

# Free-tier gate seam (todo 12) — re-exported for tests/callers.
from autoinfo.output.free_tier import (  # noqa: E402  (import at module top)
    FreeTierLimitError as FreeTierLimitError,
)
from autoinfo.output.free_tier import (
    check_free_tier_generation as check_free_tier_generation,
)
from autoinfo.prompts import get_prompt as get_prompt
from autoinfo.prompts import render_prompt as render_prompt
from autoinfo.quality_constraints import (
    EDITORIAL_OPENING_HEDGE_CONSTRAINT,
    FEATURE_STORY_GROUNDING_CONSTRAINT,
    NO_FABRICATION_CONSTRAINT,
    SYNTHESIS_ENTITY_GROUNDING_CONSTRAINT,
    SYNTHESIS_SIGNAL_TRACEABILITY_CONSTRAINT,
)
from autoinfo.quality_constraints import (
    URL_VERBATIM_CONSTRAINT as URL_VERBATIM_CONSTRAINT,
)

# Section parser — canonical module re-exported so every historical copy now
# shares ONE implementation (#400). The ``X as X`` idiom keeps each name a
# module attribute for callers/tests and for static analysis.
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

logger = logging.getLogger(__name__)

# Demo-domain seed directory (issue #319): the same seed ``init`` reads when
# scaffolding a domain.  Used as the exclude_keywords fallback so existing
# projects whose runtime config predates the field still filter noise.

# Generic theme labels that never name a meaningful report section (issue #9).
# They come from auto-discovery keyword fragments (e.g. ``new``, ``year``,
# ``user``, ``market``) whose normalized form is a bare generic word.  A group
# whose normalized theme lands here is dropped in ``_merge_theme_groups`` and
# its entries reassigned to the nearest surviving group or "Additional Topics".
_GENERIC_THEME_LABELS: Final[frozenset[str]] = frozenset(
    {
        "new",
        "year",
        "the year",
        "user",
        "activity",
        "growth",
        "apps",
        "market",
        "update",
        "summary",
    }
)

# Theme synonym map (issue #9): canonical spelling -> the key every variant
# normalizes to.  Applied in ``_normalize_theme_text`` BEFORE the near-dup
# pass so synonym variants merge in the exact-name pass (e.g. ``Year`` and
# ``The Year`` collapse onto one group before the blocklist runs).
_THEME_SYNONYMS: Final[dict[str, str]] = {
    "year": "the year",
    "ml": "machine learning",
    "llm": "large language models",
}

# Structural catch-all themes the report/product templates render as their
# own sections.  Exempt from the generic-label blocklist (they are not
# keyword-derived noise) and excluded when deciding whether a keyword
# grouping found any meaningful theme at all.
_STRUCTURAL_THEME_LABELS: Final[frozenset[str]] = frozenset(
    {
        "general",
        "additional topics",
    }
)


def _fire_agent_notification(event: str, output: Any, product_id: str) -> None:
    """Fire a fire-and-forget agent callback for a just-generated product.

    The event is persisted to the durable outbox (SQLite) BEFORE any
    delivery attempt; a background worker performs the HTTP POST. This
    hook NEVER raises — generation success is inviolable. Failures are
    logged and counted via the ``outbox_persist_failures_total`` metric
    (a row lost here never reaches the drain, so ``delivery_failures_total``
    cannot observe it).

    The return value is deliberately discarded: a lost notification must not
    fail product generation. That is why the loss is counted and logged with
    ``product_id`` rather than raised (#395).
    """
    try:
        from autoinfo.agent_callback import enqueue_agent_notification

        enqueue_agent_notification(
            event=event,
            payload=output,
            trace_id=str(uuid.uuid4()),
            product_id=product_id,
        )
    except Exception:
        logger.warning(
            "Failed to enqueue agent notification for event %r (product %s)",
            event,
            product_id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Agent-native JSON-LD constants (single source of truth)
# ---------------------------------------------------------------------------
# One @context/@type pair per agent-native payload kind, defined once so the
# identifiers cannot drift between producers. Producers MUST spread the
# constant FIRST (before "uuid") to keep @context/@type/uuid as the leading
# keys — that key order is part of the serialized output contract.


# Optional per-product analysis keys of the digest JSON-LD shape (spec §2.4,
# todo 7; surfaced into the agent payload by _render_agent_json, todo 22;
# pinned by docs/schemas/knowledge-digest-v1.json, todo 23). Emitted on
# product paths ONLY (premium-briefing / enterprise-briefing /
# magazine-digest) when the synthesis carries them; ABSENT from default
# digest/report agent output (round-trip contract — see
# TestAgentProductFields.test_default_*_agent_output_unchanged). Deliberately
# NOT runtime values of _JSONLD_DIGEST: this dict is spread verbatim into
# every agent payload, so carrying the keys here would leak them into default
# output and break the serialized contract. Shapes:
#   implications:    list[str]            # "so-what" per key_findings entry
#   risks:           list[dict[str, str]] # title / likelihood / impact / mitigation
#   action_required: list[str]            # action per key_findings entry
#   key_metrics:     list[dict[str, str]] # metric / value / source (enterprise)

# Per-product analysis fields shared by the agent JSON-LD payload
# (_render_agent_json) and the KB metadata persistence (_persist_product_analysis_to_kb).


# ---------------------------------------------------------------------------
# Delivery gate output container
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Shared entry-filter kernel (extracted to autoinfo.output.entries, T10)
# ---------------------------------------------------------------------------
# The entry-filter implementation now lives in ``autoinfo.output.entries``.
# Every moved name is re-exported here so callers (digest/report/product
# generators, CLI, MCP server, tests) keep using
# ``from autoinfo.output import ...`` unchanged.  The module-boundary tests
# patch seams on ``autoinfo.output`` (e.g. ``autoinfo.output.get_config_path``
# / ``autoinfo.output.datetime``), so the relocated functions resolve them
# through this package namespace via added function-local imports.
from autoinfo.output.entries import _CJK_EXEMPT_DOMAINS as _CJK_EXEMPT_DOMAINS  # noqa: E402
from autoinfo.output.entries import _CJK_RE as _CJK_RE  # noqa: E402
from autoinfo.output.entries import _DOMAIN_DISPLAY_NAMES as _DOMAIN_DISPLAY_NAMES  # noqa: E402
from autoinfo.output.entries import _LANG_ALIASES as _LANG_ALIASES  # noqa: E402
from autoinfo.output.entries import _LANG_DISPLAY_NAMES as _LANG_DISPLAY_NAMES  # noqa: E402
from autoinfo.output.entries import _LANG_TEACHING_SIGNALS as _LANG_TEACHING_SIGNALS  # noqa: E402
from autoinfo.output.entries import (  # noqa: E402
    _LANGUAGE_COLLAPSE_MAX_KEPT as _LANGUAGE_COLLAPSE_MAX_KEPT,
)
from autoinfo.output.entries import (  # noqa: E402
    _LANGUAGE_COLLAPSE_MIN_INPUT as _LANGUAGE_COLLAPSE_MIN_INPUT,
)
from autoinfo.output.entries import _LANGUAGE_NAMES as _LANGUAGE_NAMES  # noqa: E402
from autoinfo.output.entries import _LEAK_ERROR_TEXT_RE as _LEAK_ERROR_TEXT_RE  # noqa: E402
from autoinfo.output.entries import _LEAK_FENCED_JSON_RE as _LEAK_FENCED_JSON_RE  # noqa: E402
from autoinfo.output.entries import _LEAK_JSON_PREFIX_RE as _LEAK_JSON_PREFIX_RE  # noqa: E402
from autoinfo.output.entries import _LEAK_PROMPT_ECHO_RE as _LEAK_PROMPT_ECHO_RE  # noqa: E402
from autoinfo.output.entries import _NEAR_DUP_CHAR_SIM_MAX as _NEAR_DUP_CHAR_SIM_MAX  # noqa: E402
from autoinfo.output.entries import _NEAR_DUP_WINDOW_DAYS as _NEAR_DUP_WINDOW_DAYS  # noqa: E402
from autoinfo.output.entries import _NO_CONTENT_SUMMARY_RE as _NO_CONTENT_SUMMARY_RE  # noqa: E402
from autoinfo.output.entries import _PLATFORM_DISPLAY_NAMES as _PLATFORM_DISPLAY_NAMES  # noqa: E402
from autoinfo.output.entries import _SUMMARY_PLACEHOLDER_RE as _SUMMARY_PLACEHOLDER_RE  # noqa: E402
from autoinfo.output.entries import _TEST_SOURCE_PLATFORMS as _TEST_SOURCE_PLATFORMS  # noqa: E402
from autoinfo.output.entries import _TEST_TITLE_MARKERS as _TEST_TITLE_MARKERS  # noqa: E402
from autoinfo.output.entries import _TEST_TITLE_RE as _TEST_TITLE_RE  # noqa: E402
from autoinfo.output.entries import _TEST_TITLE_SUBSTRINGS as _TEST_TITLE_SUBSTRINGS  # noqa: E402
from autoinfo.output.entries import _TEST_URL_MARKERS as _TEST_URL_MARKERS  # noqa: E402
from autoinfo.output.entries import _TITLE_PLACEHOLDER_RE as _TITLE_PLACEHOLDER_RE  # noqa: E402
from autoinfo.output.entries import (  # noqa: E402
    _config_declares_default_language as _config_declares_default_language,
)
from autoinfo.output.entries import (  # noqa: E402
    _config_declares_exclude_keywords as _config_declares_exclude_keywords,
)
from autoinfo.output.entries import (  # noqa: E402
    _config_declares_relevance_floor as _config_declares_relevance_floor,
)
from autoinfo.output.entries import _contains_raw_llm_leak as _contains_raw_llm_leak  # noqa: E402
from autoinfo.output.entries import (  # noqa: E402
    _converge_near_duplicates as _converge_near_duplicates,
)
from autoinfo.output.entries import (  # noqa: E402
    _cross_domain_shared_language as _cross_domain_shared_language,
)
from autoinfo.output.entries import _domain_display_name as _domain_display_name  # noqa: E402
from autoinfo.output.entries import _enrich_entry_content as _enrich_entry_content  # noqa: E402
from autoinfo.output.entries import _enrich_product_entries as _enrich_product_entries  # noqa: E402
from autoinfo.output.entries import _entry_custom_fields as _entry_custom_fields  # noqa: E402
from autoinfo.output.entries import (  # noqa: E402
    _entry_matches_exclude_keywords as _entry_matches_exclude_keywords,
)
from autoinfo.output.entries import _entry_source_cell as _entry_source_cell  # noqa: E402
from autoinfo.output.entries import _extract_proper_nouns as _extract_proper_nouns  # noqa: E402
from autoinfo.output.entries import _filter_digest_entries as _filter_digest_entries  # noqa: E402
from autoinfo.output.entries import (  # noqa: E402
    _filter_entries_by_domain_exclusions as _filter_entries_by_domain_exclusions,
)
from autoinfo.output.entries import (  # noqa: E402
    _filter_entries_by_language as _filter_entries_by_language,
)
from autoinfo.output.entries import (  # noqa: E402
    _filter_entries_by_language_product_safe as _filter_entries_by_language_product_safe,
)
from autoinfo.output.entries import (  # noqa: E402
    _filter_foreign_language_teaching_entries as _filter_foreign_language_teaching_entries,
)
from autoinfo.output.entries import _filter_product_entries as _filter_product_entries  # noqa: E402
from autoinfo.output.entries import (  # noqa: E402
    _get_domain_exclude_keywords as _get_domain_exclude_keywords,
)
from autoinfo.output.entries import (  # noqa: E402
    _get_domain_relevance_floor as _get_domain_relevance_floor,
)
from autoinfo.output.entries import _has_death_event_word as _has_death_event_word  # noqa: E402
from autoinfo.output.entries import _is_empty_content as _is_empty_content  # noqa: E402
from autoinfo.output.entries import _is_empty_summary as _is_empty_summary  # noqa: E402
from autoinfo.output.entries import (  # noqa: E402
    _is_synthesized_digest_entry as _is_synthesized_digest_entry,
)
from autoinfo.output.entries import _is_test_entry as _is_test_entry  # noqa: E402
from autoinfo.output.entries import _lang_display_name as _lang_display_name  # noqa: E402
from autoinfo.output.entries import _normalize_lang as _normalize_lang  # noqa: E402
from autoinfo.output.entries import _platform_name as _platform_name  # noqa: E402
from autoinfo.output.entries import (  # noqa: E402
    _resolve_effective_language as _resolve_effective_language,
)
from autoinfo.output.entries import _resolve_gloss_language as _resolve_gloss_language  # noqa: E402
from autoinfo.output.entries import (  # noqa: E402
    _seed_domain_default_language as _seed_domain_default_language,
)
from autoinfo.output.entries import (  # noqa: E402
    _seed_domain_exclude_keywords as _seed_domain_exclude_keywords,
)
from autoinfo.output.entries import (  # noqa: E402
    _seed_domain_relevance_floor as _seed_domain_relevance_floor,
)
from autoinfo.output.entries import (  # noqa: E402
    _try_notify_content_ready as _try_notify_content_ready,
)
from autoinfo.output.entries import _user_source_label as _user_source_label  # noqa: E402
from autoinfo.output.entries import _warn_cjk_leak as _warn_cjk_leak  # noqa: E402

# ---------------------------------------------------------------------------
# D1 section detection on the rendered body (issue #298 — layer 2)
# ---------------------------------------------------------------------------
# The parser now lives in ``autoinfo.section_parser`` and is re-exported at
# module top (issue #400): ONE implementation shared with
# ``autoinfo.delivery.gate_report`` and ``scripts/validation_delivery.py``.
# D1 completeness is checked against the RENDERED body, not just the LLM
# synthesis dict — a body that is empty/garbled but whose synthesis dict is
# non-empty must fail D1.

# HTML element names are a closed set while LLM placeholders are open-ended,
# so preserving the former cannot regress on a new placeholder name.
# Issue #645: without this guard the cleaner ate <head>/<title>/<h1> from
# rendered HTML, failing the L2 structural check for every :html product.
_HTML_ELEMENT_NAMES: Final = frozenset(
    """
    html head title meta link style script body base
    header nav main article aside footer section div span
    h1 h2 h3 h4 h5 h6 p br hr pre code kbd samp var
    a em strong b i u s small mark sub sup q cite dfn abbr time
    ul ol li dl dt dd figure figcaption blockquote
    table caption thead tbody tfoot tr th td colgroup col
    img picture source video audio track iframe embed canvas svg
    path circle rect line polyline polygon g def use symbol
    form label input button select option optgroup textarea fieldset legend
    details summary dialog template slot address
    """.split()
)

_SKELETON_TOKEN_RE = re.compile(r"<([a-z][a-z0-9 _\-]+)>", re.IGNORECASE)


def _is_html_document(text: str) -> bool:
    """True when *text* is a rendered HTML document, not markdown prose."""
    lowered = text[:2000].lower()
    return "<!doctype html" in lowered or "<html" in lowered


def _strip_skeleton_token(match: re.Match[str]) -> str:
    return match.group(0) if match.group(1).strip().lower() in _HTML_ELEMENT_NAMES else ""


def _clean_skeleton_placeholders(text: str) -> str:
    """Strip LLM skeleton placeholders (``<finding 1>``, ``<metric>``, etc.)
    that the model echoed verbatim from the prompt template.

    Real HTML tags are preserved (issue #645) — the cleaner runs over
    rendered HTML documents, where ``<head>``/``<title>``/``<h2>`` are
    document structure, not placeholders.

    Returns the cleaned text with placeholder tokens removed.  Lines that
    become empty after stripping are removed.  Table rows that become
    all-pipes are removed.
    """
    # Only an HTML document has real tags to protect.  In markdown prose a
    # bare ``<source>``/``<metric>`` is the LLM echoing a prompt placeholder,
    # and some names (``source``, ``summary``) are both.
    strip = _strip_skeleton_token if _is_html_document(text) else (lambda _m: "")
    lines = text.split("\n")
    cleaned: list[str] = []
    for line in lines:
        new_line = _SKELETON_TOKEN_RE.sub(strip, line)
        # Collapse runs of whitespace left by removal
        new_line = re.sub(r"  +", " ", new_line).strip()
        # Remove empty table rows (e.g. "| | | |" → empty)
        if re.match(r"^[\s|]*$", new_line):
            continue
        # Remove empty list items (e.g. "- " after stripping)
        if re.match(r"^[-*]\s*$", new_line):
            continue
        cleaned.append(new_line)
    return "\n".join(cleaned)


# Issue #77: internal "Entry N" placeholders the LLM may echo from the prompt
# ("Source: Entry 1/16/29" in enterprise key-metrics / references).  The
# prompt now instructs real source names, but a deterministic postprocess is
# the grep-level guarantee the acceptance scan demands.
_ENTRY_N_RE = re.compile(r"(?i)Source:\s*Entry\s+\d+(?:\s*/\s*\d+)*")


def _strip_entry_placeholders(text: str) -> str:
    """Replace LLM-echoed internal ``Source: Entry N`` placeholders with a
    neutral source marker in rendered markdown (backup issue #77).

    Applied only to rendered product text — never to JSON/agent payloads,
    where such a string would be legitimate structured content.
    """
    return _ENTRY_N_RE.sub("Source: (source)", text)


def _strip_fake_source_placeholders(text: str) -> str:
    """Remove literal non-URL ``(Source: ...)`` placeholders from product text.

    Issue #165: the model emits ``(Source: TechCrunch URL)`` — a literal
    text placeholder, not a clickable citation.  Reuse the correct
    ``_FABRICATED_SOURCE_RE`` (its ``\\s*`` sits INSIDE the negative
    lookahead, so real http(s) URLs and markdown links are preserved while
    any other ``(Source: X)`` payload is stripped).
    """
    return _FABRICATED_SOURCE_RE.sub("", text)


# Issue #131: the LLM echoes the synthesis prompt's "Entry N" numbering into
# key_metrics[].source (e.g. "Cochrane review (Entry 1)", "Meta-analysis
# (Entry 13)").  Internal KB row references must never reach end users —
# strip the parenthetical ``(Entry N)`` suffix/inline markers.  Unlike
# ``_ENTRY_N_RE`` (which only matches the ``Source: Entry N`` prefix form),
# this also handles the trailing ``(Entry N)`` shape the metrics table
# carries.
_ENTRY_REF_RE: Final = re.compile(r"\(?\s*(?i:Entry)\s+\d+(?:\s*/\s*\d+)*\s*\)?")


def _strip_entry_refs(text: str) -> str:
    """Remove LLM-echoed internal ``Entry N`` references from a source field.

    Only trims trailing whitespace when nothing was removed, so legitimate
    punctuation (a closing period/paren) is preserved for clean text.
    """
    if not text:
        return text or ""
    cleaned = _ENTRY_REF_RE.sub("", text)
    if cleaned == text:
        return text
    # An Entry reference was removed — collapse leftover whitespace and drop
    # the dangling punctuation that preceded it ("(Entry 1)." -> "...").
    return re.sub(r"\s{2,}", " ", cleaned).strip(" .,;:").strip()


# Issue #93: presentation provenance fabrication — a (Source: X) citation
# where X is not a real http(s) URL (e.g. "KB: <title>", "KB-N",
# "knowledgebase.local", a bare media/person name) is fabricated and must
# be removed from the rendered deck.  \s* is INSIDE the negative lookahead
# so a real URL is never consumed (a leading space must not let the
# lookahead pass); only non-URL citations are stripped.
_FABRICATED_SOURCE_RE = re.compile(r"\(Source:(?!\s*(?:https?://|\[))[^)\n]*\)", re.IGNORECASE)

# Backup issue #101: the shape pass above only rejects citations that are
# NOT URL-shaped.  A well-formed but fabricated URL (e.g.
# "https://www.news.com/<slug>", "https://example.com/kb/N") still passes.
# This domain-level backstop cross-checks every rendered (Source: URL)
# against the real KB source_url whitelist used in the prompt.
_PRESENTATION_SOURCE_START_RE = re.compile(r"\(Source:", re.IGNORECASE)
_PRESENTATION_CITATION_URL_RE = re.compile(r"https?://[^)\s]+", re.IGNORECASE)


def _source_url_verifiable(url: str, allowed_urls: set[str]) -> bool:
    """Return True when *url* matches a real KB source_url in *allowed_urls*.

    Fast path is exact equality (the LLM copies the URL we fed it).  Near
    variants (trailing slash, query, fragment, host-only prefix) count only
    when the extra suffix is a path-separated boundary — a generic domain
    root is never accepted as a citation for a specific article.
    """
    candidate = url.rstrip(".,;:!?)]").rstrip("/")
    for real in allowed_urls:
        real_norm = real.rstrip("/")
        if candidate == real_norm:
            return True
        longer, shorter = (
            (real_norm, candidate) if len(real_norm) >= len(candidate) else (candidate, real_norm)
        )
        boundary = longer[len(shorter) : len(shorter) + 1]
        if longer.startswith(shorter) and boundary in ("/", "?", "#"):
            return True
    return False


def _strip_unverifiable_presentation_sources(text: str, allowed_urls: set[str]) -> str:
    """Drop (Source: URL) citations whose URL is not verifiable against the
    real KB source_url whitelist (backup issue #101 backstop).

    Only the citation marker is removed — the bullet text stays and the
    source mechanism itself is preserved for bullets that carry a real URL
    (deleting the whole Source mechanism is a degradation, #b2b/#french).
    """
    if not allowed_urls:
        return text
    out: list[str] = []
    pos = 0
    for m in _PRESENTATION_SOURCE_START_RE.finditer(text):
        out.append(text[pos : m.start()])
        # Scan to the citation's closing paren, allowing one level of nested
        # parens (markdown link "[text](url)") so the citation is consumed whole.
        j = m.end()
        depth = 1
        while j < len(text) and depth:
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
            j += 1
        citation = text[m.start() : j]
        urls = _PRESENTATION_CITATION_URL_RE.findall(citation)
        keep = bool(urls) and all(_source_url_verifiable(u, allowed_urls) for u in urls)
        out.append(citation if keep else _CITATION_RESIDUE_MARK)
        pos = j
    out.append(text[pos:])
    return _clean_citation_residue("".join(out))


def _sanitize_presentation_sources(text: str, allowed_urls: set[str] | None = None) -> str:
    """Strip fabricated source citations from rendered presentation
    text (backup issue #93).

    The LLM may substitute human-readable names for URLs ("(Source: Inside
    Higher Ed)", "(Source: KB-N)", "(Source: knowledgebase.local/x)") even
    when the prompt demands real URLs.  A deterministic post-pass removes
    any ``(Source: ...)`` that is not an http(s) URL or markdown link — the
    grep-level guarantee the acceptance scan demands.  When *allowed_urls*
    (the real KB source_url set) is supplied, additionally strips URL-shaped
    citations that are NOT verifiable against that whitelist — a well-formed
    but fabricated placeholder never ships (backup issue #101).  Never
    applied to JSON/agent payloads.
    """
    text = _FABRICATED_SOURCE_RE.sub(_CITATION_RESIDUE_MARK, text)
    if allowed_urls:
        text = _strip_unverifiable_presentation_sources(text, allowed_urls)
    return _clean_citation_residue(text)


# Issue #207 (backup): report/digest body citations.  A body citation is
# "(Source: URL)", "(Sources: URL and URL)", or "[label](URL)".  The report
# synthesis once re-slugged a real TechCrunch URL into a fabricated
# "…/a16z-brings-growth-fund-to-8-5b-days-after-launching-a-new-1-1b-fund/"
# (HTTP 404) that quality_gate C5 only caught post-hoc.  These regexes pick
# an http(s) URL out of a "(Source[s]: …)" citation and a "[label](URL)"
# markdown link, respectively.
_REPORT_SOURCE_START_RE = re.compile(r"\(Source[s]?:", re.IGNORECASE)
_REPORT_CITE_URL_RE = re.compile(r"https?://[^)\s]+", re.IGNORECASE)
_REPORT_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")

# Issue #644: dropping a citation used to leave its surrounding separators
# behind ("all feature , , ." / "exposure  and").  The junction where a
# citation was removed is marked with a sentinel so cleanup stays scoped to
# that spot — a legitimate comma list elsewhere in the same text is never
# touched.
_CITATION_RESIDUE_MARK = "\x00"


def _clean_citation_residue(text: str) -> str:
    """Tidy the separators left behind by removed citations."""
    out = text
    previous = None
    while previous != out:
        previous = out
        out = re.sub(
            rf"(?:{_CITATION_RESIDUE_MARK}[ \t]*,?[ \t]*){{2,}}",
            _CITATION_RESIDUE_MARK,
            out,
        )
    out = re.sub(rf"[ \t]*{_CITATION_RESIDUE_MARK}[ \t]*,", ",", out)
    out = re.sub(rf"[ \t]*{_CITATION_RESIDUE_MARK}[ \t]*(?=[.,;:!?])", "", out)
    out = re.sub(rf"(?m)^[ \t]*{_CITATION_RESIDUE_MARK}[ \t]*", "", out)
    out = re.sub(rf"[ \t]*{_CITATION_RESIDUE_MARK}[ \t]*", " ", out)
    return out.replace(_CITATION_RESIDUE_MARK, " ")


def _sanitize_report_urls(text: str, allowed_urls: set[str]) -> str:
    """Strip fabricated body-cited URLs from rendered report/digest text.

    A deterministic post-synthesis backstop (issue #207, mirror of the #93/#101
    presentation sanitizer): every body citation URL — ``(Source: URL)``,
    ``(Sources: URL and URL)``, and ``[label](URL)`` — is cross-checked against
    the real KB ``source_url`` *allowed_urls* whitelist.  A URL that is NOT
    verifiable against the whitelist (prefix-aligned, path-boundary match via
    :func:`_source_url_verifiable`) is dropped so a fabricated slug never ships:

    - an unverifiable ``(Source: …)`` / ``(Sources: …)`` citation is removed
      whole (the surrounding bullet text stays, mirroring
      ``_strip_unverifiable_presentation_sources``);
    - an unverifiable ``[label](URL)`` markdown link is reduced to bare
      ``label`` so the human-readable label survives while the untraceable
      URL is gone.

    Never applied to JSON/agent payloads, whose URLs are already the real
    KB source_urls (never LLM-composed).
    """
    if not allowed_urls:
        return text
    out: list[str] = []
    pos = 0
    for m in _REPORT_SOURCE_START_RE.finditer(text):
        out.append(text[pos : m.start()])
        j = m.end()
        depth = 1
        while j < len(text) and depth:
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
            j += 1
        citation = text[m.start() : j]
        urls = _REPORT_CITE_URL_RE.findall(citation)
        keep = bool(urls) and all(_source_url_verifiable(u, allowed_urls) for u in urls)
        out.append(citation if keep else _CITATION_RESIDUE_MARK)
        pos = j
    out.append(text[pos:])
    text = _clean_citation_residue("".join(out))

    def _replace(match: re.Match[str]) -> str:
        url = match.group(2).rstrip(".,;:!?)]").rstrip("/")
        if _source_url_verifiable(url, allowed_urls):
            return match.group(0)
        return match.group(1)

    return _REPORT_MD_LINK_RE.sub(_replace, text)


# Minimum content substance for a PROCESSED markdown/html product (issue #298).


# ---------------------------------------------------------------------------
# LLM product judge (issue #298 — layer 3, optional)
# ---------------------------------------------------------------------------


#: An entry counts as usable source when it carries a ``source_url`` or a real
#: summary. Provenance, not title length: against ``autoinfo.db`` (1821 entries,
#: 23 domains) a title-length threshold also rejected legitimately terse entries
#: such as a 7-character headline, while this rule isolates exactly the 9 rows
#: that have neither provenance nor content -- ``Test Entry``, ``QA Article``,
#: ``Entry A/B``, ``x``, ``y``. Every one of those is a test artifact.
#: The architecture already makes provenance mandatory for a 01-Raw entry, so
#: this reuses that rule rather than inventing a second one.

#: Source/title markers that identify a synthetic test fixture rather than
#: collected material. Matched case-insensitively against title and source_url.
#: The tier-matrix fixtures spell their name two ways -- ``KB Tier Matrix``
#: (spaced) in the title and ``kb-tier-matrix.autoinfo.dev`` (hyphenated) in the
#: URL -- so both forms must be listed or one of them slips through.


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# KB export family (extracted to autoinfo.output.export, T7)
# ---------------------------------------------------------------------------
# The export implementation now lives in ``autoinfo.output.export``.  Every
# moved name is re-exported here so callers (CLI, MCP server, delivery
# channels, tests) keep using ``from autoinfo.output import ...`` unchanged.
# The module-boundary tests patch these seams on ``autoinfo.output`` (e.g.
# ``autoinfo.output.get_config_path`` / ``autoinfo.output.KBStore``), so the
# relocated functions resolve them through this package namespace via added
# function-local imports.
from autoinfo.output.export import _ENTRIES_TABLE_DDL as _ENTRIES_TABLE_DDL  # noqa: E402
from autoinfo.output.export import _build_bundle_json as _build_bundle_json  # noqa: E402
from autoinfo.output.export import _build_bundle_markdown as _build_bundle_markdown  # noqa: E402
from autoinfo.output.export import _build_bundle_metadata as _build_bundle_metadata  # noqa: E402
from autoinfo.output.export import _build_bundle_pdf as _build_bundle_pdf  # noqa: E402
from autoinfo.output.export import (  # noqa: E402
    _create_filtered_sqlite_copy as _create_filtered_sqlite_copy,
)
from autoinfo.output.export import _derive_export_lang as _derive_export_lang  # noqa: E402
from autoinfo.output.export import _export_agent_json as _export_agent_json  # noqa: E402
from autoinfo.output.export import _export_bundle as _export_bundle  # noqa: E402
from autoinfo.output.export import _export_csv as _export_csv  # noqa: E402
from autoinfo.output.export import _export_epub as _export_epub  # noqa: E402
from autoinfo.output.export import _export_graphml as _export_graphml  # noqa: E402
from autoinfo.output.export import _export_json as _export_json  # noqa: E402
from autoinfo.output.export import _export_markdown as _export_markdown  # noqa: E402
from autoinfo.output.export import _export_mobi as _export_mobi  # noqa: E402
from autoinfo.output.export import _export_pdf as _export_pdf  # noqa: E402
from autoinfo.output.export import _export_rss as _export_rss  # noqa: E402
from autoinfo.output.export import _export_sitemap as _export_sitemap  # noqa: E402
from autoinfo.output.export import _export_sqlite as _export_sqlite  # noqa: E402
from autoinfo.output.export import _list_domains_from_db as _list_domains_from_db  # noqa: E402
from autoinfo.output.export import _parse_tags_list as _parse_tags_list  # noqa: E402
from autoinfo.output.export import _run_pdf_with_timeout as _run_pdf_with_timeout  # noqa: E402
from autoinfo.output.export import _wal_checkpoint as _wal_checkpoint  # noqa: E402
from autoinfo.output.export import export_kb as export_kb  # noqa: E402

# ---------------------------------------------------------------------------
# Digest generation
# ---------------------------------------------------------------------------

PERIOD_DAYS: dict[str, int] = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
}

PERIOD_LABELS: dict[str, str] = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
}


def _compute_date_range(period: str) -> tuple[str, str]:
    """Return (date_from, date_to) ISO strings for the given period.

    Parameters
    ----------
    period:
        One of ``"daily"``, ``"weekly"``, ``"monthly"``.

    Returns
    -------
    tuple[str, str]
        ``(date_from, date_to)`` — ``date_from`` is *period* days ago,
        ``date_to`` is today (both as ``YYYY-MM-DD``).
    """
    days = PERIOD_DAYS.get(period, 7)
    today = date.today()
    date_from = (today - timedelta(days=days)).isoformat()
    date_to = today.isoformat()
    return date_from, date_to


def _curated_sort_key(entry: dict[str, Any]) -> tuple[float, str]:
    """Sort key for curated consumption: relevance desc, stable tie by entry_id."""
    score = entry.get("relevance_score")
    try:
        quality = float(score) if score is not None else 0.0
    except (TypeError, ValueError):
        quality = 0.0
    return (-quality, str(entry.get("entry_id", "")))


def _filter_entries_by_content_preference(
    entries: list[dict[str, Any]],
    content_preference: str,
) -> list[dict[str, Any]]:
    """Filter KB entries by the end-user ``content_preference`` tier policy.

    - ``"raw_only"``: keep only 01-Raw tier entries.
    - ``"processed_only"``: keep 02-Draft and 03-Wiki tier entries with
      curated-priority consumption: 03-Wiki entries come first (sorted by
      relevance desc, stable ties), 02-Draft entries fill the remainder.
      Each selected entry carries ``source_tier`` — ``"curated"`` for
      Wiki, ``"fresh"`` for Draft — for tier badge rendering.
    - ``"both"`` (or any unknown value): return entries unchanged.

    The input list is not mutated.
    """
    if content_preference == "raw_only":
        return [e for e in entries if e.get("tier", "") == "01-Raw"]
    if content_preference == "processed_only":
        wiki = sorted(
            (e for e in entries if e.get("tier", "") == "03-Wiki"),
            key=_curated_sort_key,
        )
        draft = sorted(
            (e for e in entries if e.get("tier", "") == "02-Draft"),
            key=_curated_sort_key,
        )
        return [
            *({**e, "source_tier": "curated"} for e in wiki),
            *({**e, "source_tier": "fresh"} for e in draft),
        ]
    return entries


def _source_tier_badge_enabled() -> bool:
    """Resolve ``output.source_tier_badge`` from config (default True)."""
    try:
        config_path = get_config_path()
        if config_path is not None:
            return bool(load_config(config_path).output.source_tier_badge)
    except Exception:
        logger.debug(
            "Failed to load output.source_tier_badge, defaulting to True",
            exc_info=True,
        )
    return True


def _output_config_ref_limit() -> int:
    """Resolve ``output.ref_limit`` from config (default 60).

    The CLI/MCP default path (no explicit ``ref_limit`` param) falls back
    to the project config's ``output.ref_limit``, which defaults to 60
    (issue #11 — references render uncapped).
    """
    try:
        config_path = get_config_path()
        if config_path is not None:
            return int(load_config(config_path).output.ref_limit)
    except Exception:
        logger.debug(
            "Failed to load output.ref_limit, defaulting to 60",
            exc_info=True,
        )
    return 60


def _ref_sort_key(e: dict[str, Any]) -> tuple[bool, float]:
    """Deterministic References sort key: (has summary desc, relevance desc)."""
    return (
        bool(str(e.get("summary") or "").strip()),
        float(e.get("relevance_score") or 0.0),
    )


# --- Low-value reference relegation (issue #42) ------------------------------
# Paid-user audit flagged References entries that are URL-valid + real but
# off-domain noise for commercial domains: promos / ticket sales (``save up to
# $300 on a TechCrunch Disrupt pass``), obituaries (``Dolly Parton ... has died
# at age 80``), and celebrity/entertainment fluff.  These entries are NOT
# deleted (traceability stays in Raw) — they are re-ranked to the tail of the
# References list and, for non-language-learning domains with enough real
# entries, dropped from References entirely.
#
# Signals are PHRASE-SHAPED (issue #42 Do-NOT): bare words like ``died`` /
# ``discount`` are deliberately NOT used, so a legit sentence ("pricing models
# to promote value", "discounts up to 10% in regions") never fires.


_REF_LOW_VALUE_PATTERNS: dict[str, tuple[str, ...]] = {
    "promo": (
        r"save up to",
        r"save\s+\$",
        r"\blast chance\b",
        r"\bdisrupt pass\b",
        r"\bregister now\b",
        r"\bearly access\b",
        r"\bgiveaway",
        r"\bsale ends\b",
        r"\bcoupon\b",
        r"\bdeal of the (?:day|week)\b",
        r"\btickets? (?:on sale|available|now|remaining)\b",
        r"(?:buy|book|purchase|grab|secure|get) (?:your )?tickets?",
        r"\bdiscount (?:code|coupon|offer|of \d+%?|\d+%? off)\b",
        r"\d+%?\s*discount\b",
    ),
    "obituary": (
        r"\bdied\b",
        r"\bhas died\b",
        r"\bdied at age\b",
        r"\bdies at\b",
        r"\bdeath of\b",
        r"\bobituary\b",
        r"\bfuneral\b",
        r"\bin memoriam\b",
    ),
    "celebrity": (
        r"\bcelebrity\b",
        r"\bdolly parton\b",
        r"\bdavid bowie\b",
        r"\bfilm star\b",
        r"\bhollywood\b",
        r"\bpop star\b",
        r"\breality tv\b",
    ),
}

_COMPILED_LOW_VALUE_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    category: [re.compile(p, re.IGNORECASE) for p in patterns]
    for category, patterns in _REF_LOW_VALUE_PATTERNS.items()
}

_REF_LOW_VALUE_CONTEXT_CHARS = 200
_REF_LOW_VALUE_MIN_REAL_ENTRIES = 20


def _low_value_signal_penalty(entry: dict[str, Any]) -> int:
    """Score *entry* on the phrase-shaped low-value signals (issue #42).

    Returns the number of distinct low-value categories (promo / obituary /
    celebrity) matched across the title + first ~200 chars of the
    summary/content.  0 = clean.  Deterministic: no LLM, no randomness.
    """
    haystack = " ".join(
        filter(
            None,
            (
                str(entry.get("title") or ""),
                str(entry.get("summary") or "")[:_REF_LOW_VALUE_CONTEXT_CHARS],
                str(entry.get("content") or "")[:_REF_LOW_VALUE_CONTEXT_CHARS],
            ),
        )
    )
    return sum(
        1
        for patterns in _COMPILED_LOW_VALUE_PATTERNS.values()
        if any(p.search(haystack) for p in patterns)
    )


def _select_family_entry_subset(
    entries: list[dict[str, Any]], product_family: str
) -> list[dict[str, Any]]:
    """Select a differentiated entry subset per briefing family (issue #145).

    Premium and enterprise briefings previously shared the SAME reference
    set (both derived from the full entry list), so the two paid products
    were the same content in a different layout.  Prompt-only scope
    directives (#140) could not fix this — references are fixed at the data
    layer before the prompt runs.

    This is the data-layer split: the returned subset feeds BOTH the LLM
    synthesis AND the reference derivation, so premium and enterprise source
    genuinely different entries:

    - premium-briefing: the top-relevance core (dense deep-dive material,
      ~12 entries) — "1-2 topics, deep".
    - enterprise-briefing: a relevance-tiered spread (~25 entries sampled
      across the relevance range) — "4-6 decision topics, broad".

    Other families return the input unchanged.  Deterministic, no LLM.
    """
    if product_family == "premium-briefing":
        sorted_entries = _sorted_ref_entries(entries)
        # Deep core: the top relevance entries, capped at half the corpus
        # so a small domain never yields the FULL list (issue #146 — a
        # ≤12-entry domain previously returned all entries, overlapping the
        # enterprise set 100%).
        cap = min(12, max(len(sorted_entries) // 2, 1))
        return sorted_entries[:cap]
    if product_family == "enterprise-briefing":
        sorted_entries = _sorted_ref_entries(entries)
        n = len(sorted_entries)
        premium_cap = min(12, max(n // 2, 1))
        # Enterprise excludes premium's deep core and instead covers the
        # mid-to-lower relevance range (broad decision coverage) plus a few
        # top-tier anchors.  Overlap is bounded to just the anchor count, so
        # the two briefings diverge at ANY corpus size (#146).
        mid_tail = sorted_entries[premium_cap:]
        anchor_count = max(2, min(n // 8, 5))
        anchors = sorted_entries[:: max(n // anchor_count, 1)][:anchor_count]
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for e in list(mid_tail) + list(anchors):
            u = str(e.get("source_url") or "")
            if u and u in seen:
                continue
            if u:
                seen.add(u)
            deduped.append(e)
        return deduped[:25]
    return entries


def _sorted_ref_entries(
    entries: list[dict[str, Any]], domain: str | None = None
) -> list[dict[str, Any]]:
    """Return *entries* ordered for the References list (issues #11, #42).

    Issue #11: the references context list is capped at ``ref_limit``, so the
    sort MUST run on the full ``entries`` list BEFORE the ref dicts are built
    (ref dicts drop ``relevance_score``/``summary``).  Title-only entries
    (empty summary — e.g. ProductHunt) de-prioritize below summary-bearing
    ones; the deterministic tiebreak is ``relevance_score`` desc.

    Issue #42: entries carrying low-value signals (promo / obituary /
    celebrity — see :func:`_low_value_signal_penalty`) are re-ranked AFTER
    the clean entries, so they only surface when the domain has very few real
    entries.  Language-learning domains keep their cultural/historical
    teaching material: flagged entries always stay in the returned list, at
    the tail (reduce, don't delete).  For non-language-learning domains,
    flagged entries are dropped from References entirely when the domain still
    has at least ``_REF_LOW_VALUE_MIN_REAL_ENTRIES`` clean candidates;
    otherwise a few survive at the tail rather than leaving the list sparse.
    Entries are never deleted from the KB — this only affects References
    ordering.  Deterministic: same input → same output, no LLM calls.
    """
    lang_mode = domain is None or _is_lang_learning_domain(domain or "")
    clean: list[dict[str, Any]] = []
    lang_flagged: list[dict[str, Any]] = []
    commercial_flagged: list[dict[str, Any]] = []
    for entry in entries:
        if _low_value_signal_penalty(entry) == 0:
            clean.append(entry)
            continue
        entry_domain = str(entry.get("domain") or domain or "")
        if _is_lang_learning_domain(entry_domain):
            lang_flagged.append(entry)
        else:
            commercial_flagged.append(entry)
    clean_sorted = sorted(clean, key=_ref_sort_key, reverse=True)
    drop_commercial = (
        commercial_flagged and not lang_mode and len(clean) >= _REF_LOW_VALUE_MIN_REAL_ENTRIES
    )
    kept = lang_flagged + ([] if drop_commercial else commercial_flagged)
    if not kept:
        return clean_sorted
    return clean_sorted + sorted(kept, key=_ref_sort_key, reverse=True)


def _cap_product_key_findings(
    key_findings: list[Any], references: list[dict[str, Any]]
) -> list[Any]:
    """Cap *key_findings* to ``min(MAX_FINDINGS, len(references))``.

    Issue #11 (decision a): the enterprise ``selected N of M`` label renders
    ``selected {{ key_findings|length }} of {{ references|length }}``, and the
    PRIMARY synthesis ``key_findings`` is LLM-produced and unbounded (only the
    §2.4 re-prompt is bounded by ``_DEDICATED_PRODUCT_PROMPT_MAX_FINDINGS``).
    When ``ref_limit`` drops BELOW the findings count the label would invert
    (``selected 9 of 8``).  Cap the findings in the render context to
    ``min(12, len(references))`` so the label can never invert.
    """
    cap = min(_DEDICATED_PRODUCT_PROMPT_MAX_FINDINGS, len(references))
    return list(key_findings[:cap])


def _promote_eligible_drafts(
    store: KBStore,
    domains: list[str],
    caller: str = "digest",
) -> dict[str, Any]:
    """Promote eligible 02-Draft entries for the given domains (T6 trigger).

    Best-effort promotion sweep run before entry selection: every 02-Draft
    entry is admission-checked by the existing promote path
    (:meth:`KBStore.promote_kb_draft`) inside its own try/except, so a
    rejection or an unexpected failure never blocks content generation.
    Project gate thresholds apply when a config is present (defaults
    otherwise).  Idempotent — already-promoted entries are no longer in
    02-Draft and are naturally skipped.

    Returns a summary dict ``{promoted: [entry_id], rejected:
    [{entry_id, reasons}], failed: [{entry_id, error}]}`` which callers
    may log or ignore.
    """
    summary: dict[str, Any] = {"promoted": [], "rejected": [], "failed": []}
    if not domains:
        return summary
    try:
        config_path = get_config_path()
        config = load_config(config_path) if config_path is not None else None
    except Exception:
        config = None
    for domain in domains:
        try:
            drafts = store.list_kb_tier(domain=domain, tier="02-Draft", limit=10000)
        except Exception as exc:
            logger.warning(
                "promote_eligible: could not list 02-Draft for '%s': %s",
                domain,
                exc,
            )
            continue
        for draft in drafts:
            draft_id = draft.get("entry_id", "")
            if not draft_id:
                continue
            try:
                store.promote_kb_draft(draft_id=draft_id, config=config, caller=caller)
                summary["promoted"].append(draft_id)
                logger.info(
                    "Product-driven promotion of %s (caller=%s)",
                    draft_id,
                    caller,
                )
            except PromotionRejected as exc:
                summary["rejected"].append(
                    {
                        "entry_id": draft_id,
                        "reasons": [str(r) for r in exc.reasons],
                    }
                )
            except Exception as exc:
                summary["failed"].append({"entry_id": draft_id, "error": str(exc)})
                logger.warning("Promotion failed for %s: %s", draft_id, exc)
    return summary


def _resolve_content_preference(user_id: str) -> str:
    """Resolve the end-user ``content_preference`` tier policy (B-001).

    Lazy-loads stored preferences for *user_id* via
    :func:`autoinfo.user_store.get_preferences` and resolves the effective
    ``content_preference`` via
    :func:`autoinfo.user_store.resolve_content_preference`.

    Returns ``"both"`` when *user_id* is empty, the user has no stored
    preferences, or the stored value is missing/invalid — so callers
    without a user context keep the pre-B-001 behavior (no filtering).
    """
    if not user_id:
        return "both"
    try:
        from autoinfo.user_store import (  # noqa: PLC0415
            get_preferences,
            resolve_content_preference,
        )

        prefs_result = get_preferences(user_id)
        if "preferences" in prefs_result:
            content_preference = resolve_content_preference(prefs_result["preferences"])
            logger.debug(
                "Applied stored content_preference='%s' for user '%s'",
                content_preference,
                user_id,
            )
            return content_preference
    except Exception:
        logger.debug(
            "Failed to load preferences for user '%s'",
            user_id,
            exc_info=True,
        )
    return "both"


# ---------------------------------------------------------------------------
# Template loader
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "data" / "templates"


# ---------------------------------------------------------------------------
# ProductTemplate — template selection with domain overrides
# ---------------------------------------------------------------------------

# Maps output format strings to template variant suffixes.
# E.g. format="markdown" → template variant "md" → digest.md.j2


# ---------------------------------------------------------------------------
# Product template registry
# ---------------------------------------------------------------------------


# Product family → H1 product word (issue #318, augmented #99).  Keyed by
# the family name resolved by :func:`_resolve_digest_product_type` /
# :func:`_resolve_report_product_type` (the registry row name when its flat
# template file exists, else the default family).  The default
# ``digest``/``report`` families map to their own words so the non-product
# paths keep their historical titles byte-identical.  Issue #99: tutorial
# (and presentation) were missing, so ``--product tutorial`` rendered
# "# Weekly Digest — <domain>" — every registry family carries its word now.


# ---------------------------------------------------------------------------
# LLM synthesis for digests
# ---------------------------------------------------------------------------

_DIGEST_SYSTEM_PROMPT = get_prompt("digest_system")

_DIGEST_FIELD_DESCRIPTIONS = [
    # Issue #210: the Executive Summary opener is an editorial-OPENING
    # surface — its summary voice invited unhedged market-direction/motive
    # assertions.  Hedge/grounding now pinned (mirrors editorial_intro).
    '"executive_summary": "2-3 sentence overview of the period\'s key '
    "developments grounded in the entries. " + EDITORIAL_OPENING_HEDGE_CONSTRAINT + '"',
    '"key_findings": [{"topic": "Topic name", "detail": "Key finding sentence"}], '
    "list 3-5 most important findings",
    '"trends": ["Trend or pattern observed across multiple entries"], '
    "list relevant cross-cutting trends",
    '"recommendations": ["Actionable recommendation based on the data"], '
    "list actionable recommendations if any",
]

# Product-family field sections appended to the digest synthesis prompt
# (spec §2.4, todo 7). Keyed by the resolved product family so the default
# ``digest`` family stays unchanged. ``implications`` / ``risks`` /
# ``action_required`` are index-aligned 1:1 with ``key_findings`` (spec
# §5.2-5.4 per-takeaway pairing); ``key_metrics`` is enterprise-only.
_DIGEST_PRODUCT_BASE_FIELDS: list[str] = [
    '"implications": ["So-what implication for finding 1", ...], one item per '
    "key_findings entry, index-aligned 1:1 (item N matches finding N)",
    '"risks": [{"title": "Risk title", "likelihood": "high|medium|low", '
    '"impact": "high|medium|low", "mitigation": "Mitigation action"}], '
    "one item per key_findings entry, same order",
    '"action_required": ["Action for finding 1", ...], one item per '
    "key_findings entry, index-aligned 1:1",
]

_DIGEST_ENTERPRISE_METRICS_FIELDS: list[str] = [
    '"key_metrics": [{"metric": "Metric name", "value": "Quantified value", '
    '"source": "Publication/source name of the underlying report '
    '(never placeholder text like Entry N)"}], '
    "quantified metrics only "
    "(enterprise decision-support table)",
]

# Issue #313: magazine-digest editorial framing — an editor's note framing
# the week plus a personality profile / deep-dive feature story, so the
# magazine is a narrative product rather than a bare summary list.
#
# Issue #191: feature_story must carry the SAME grounding discipline as the
# column sections (#316) — long-form narrative invites inferential wording
# ("enterprises clearly crave", "likely from media and corporate clientele")
# unless the field prompt pins it to sourced facts.  The field says what it
# must be: grounded in entries, concrete numbers/dates/companies, inference
# explicitly hedged or omitted.
_DIGEST_MAGAZINE_EDITORIAL_FIELDS: list[str] = _DIGEST_PRODUCT_BASE_FIELDS + [
    # Issue #210: the Editor's Note is an editorial-OPENING surface — its
    # "opinionated but factual" voice invited unhedged market-direction /
    # motive assertions (R6/R7: "the smart money is betting on…").  The
    # hedge constraint (#191 discipline) now pins it to sourced+hedged.
    '"editorial_intro": "A 2-3 sentence editorial introduction paragraph '
    "for this magazine edition \u2014 the editor's framing of the week, "
    "written in a magazine voice (opinionated but factual). "
    + EDITORIAL_OPENING_HEDGE_CONSTRAINT
    + '"',
    '"feature_story": "A 3-5 paragraph personality profile / deep-dive '
    "story on one notable person, company, or trend from the period, in "
    "magazine feature style \u2014 a narrative that connects and "
    "interprets the entries' stated facts. " + FEATURE_STORY_GROUNDING_CONSTRAINT + '"',
]

# Issue #316: column deep-dive sections — the column template renders a
# Deep Dive from a ``sections`` array (each ``{title, content}``), so the
# digest synthesis must request it (mirroring the #308 report-path wording).
# Issue #210: the section opener is an editorial-OPENING surface too — add
# the hedge discipline so analysis sentences never assert unhedged
# market-direction/motive judgments as fact.
_DIGEST_COLUMN_SECTIONS_FIELDS: list[str] = [
    '"sections": [{"title": "Subsection title", "content": "2-3 paragraphs '
    "of analysis grounded in specific entries \u2014 quote concrete numbers, "
    "dates, and named companies/studies from the source material; no filler "
    "paragraphs. "
    + EDITORIAL_OPENING_HEDGE_CONSTRAINT
    + '"}], 8-10 distinct deep-dive subsections, each with '
    "substantive content",
]

_DIGEST_PRODUCT_FIELD_DESCRIPTIONS: dict[str, list[str]] = {
    "premium-briefing": _DIGEST_PRODUCT_BASE_FIELDS,
    "magazine-digest": _DIGEST_MAGAZINE_EDITORIAL_FIELDS,
    "enterprise-briefing": (_DIGEST_PRODUCT_BASE_FIELDS + _DIGEST_ENTERPRISE_METRICS_FIELDS),
    "column": _DIGEST_COLUMN_SECTIONS_FIELDS,
}

# Issue #140: per-family selection-scope directive so premium and enterprise
# briefings differentiate their coverage/angle instead of reusing the same
# top entries in a different layout.  Premium = deep dive on 1-2 chosen
# topics; enterprise = decision-oriented coverage of 4-6 topics.
_DIGEST_PRODUCT_SCOPE_GUIDANCE: dict[str, str] = {
    "premium-briefing": (
        "Scope: focus on 1-2 of the most significant developments of the "
        "period. Provide deep, differentiated analysis of those chosen "
        "topics \u2014 go beyond the summary list into mechanism, context, and "
        "likely trajectory. Do not pad with minor items."
    ),
    "enterprise-briefing": (
        "Scope: cover 4-6 decision-relevant developments of the period "
        "across the domain. Prioritize items with quantified or "
        "decision-support value (metrics, regulatory, competitive), and "
        "frame each finding from a decision-maker perspective (what to "
        "watch, what it means, what to do)."
    ),
}


# ---------------------------------------------------------------------------
# Issue #203 — canonical RMB→USD annotation for synthesis context
# ---------------------------------------------------------------------------

# Chinese monetary units and the RMB amounts they denote.  ``亿元`` / bare ``亿``
# are hundred-millions of yuan; ``万元`` is ten-thousands of yuan.  This is the
# config-driven conversion (never a prompt hardcode): the rate is read from
# ``config.currency.rmb_usd_rate`` so EVERY product annotates the SAME
# canonical USD value for the same RMB amount.
_RMB_YI_RE = re.compile(r"([0-9][0-9,_]*(?:\.[0-9]+)?)\s*(亿元?)")
_RMB_WAN_RE = re.compile(r"([0-9][0-9,_]*(?:\.[0-9]+)?)\s*(万元)")

# Issue #206 — Chinese-numeral RMB amounts WITHOUT leading digits that the
# digit-led regexes above (which REQUIRE a leading ``[0-9]``) never cover:
# a bare ``千万元`` (1000万 = 10,000,000 yuan) or a bare ``亿元``
# (100,000,000 yuan).  A preceding degree word (``超/近/约/逾``) is just a
# CJK pass-through and does not change the base.  Kept CONSERVATIVE:
#     * ``数X`` forms (独具数千万元 / 数亿元) have NO reliable base and are
#       SKIPPED — a ``千万元``/``亿元`` preceded by ``数`` is not annotated.
#     * ``千万元？`` (bare ``千万``) is NOT matched — ``千万不要`` (be sure
#       not to) is a common everyday idiom, never a money amount.
#     * bare ``亿`` alone is NOT matched — ``亿万人`` counts people, not yuan.
# Each textual unit is matched as a WHOLE token (``千万元`` before ``亿元``)
# so the unit is never partially consumed.
_RMB_TEXTUAL_RE = re.compile(r"(?<![0-9数])(?:千万元|亿元)")

# Yuan per textual RMB unit (issue #206): 千万元 = 10,000,000 yuan;
# 亿元 = 100,000,000 yuan.
_TEXTUAL_RMB_BASE = {"千万元": 1e7, "亿元": 1e8}


def _get_rmb_usd_rate() -> float:
    """Resolve the canonical RMB→USD rate from config (default 7.0).

    Config-driven by design (#203): the rate is read once from
    ``currency.rmb_usd_rate`` and injected into every product's synthesis
    prompt, so products never invent their own per-product conversion.
    """
    try:
        cfg = load_config(get_config_path())  # type: ignore[arg-type]
        return float(cfg.currency.rmb_usd_rate)
    except Exception:
        return float(Config().currency.rmb_usd_rate)


def _format_usd_equivalent(usd: float) -> str:
    """Format a USD value as '⟪N⟫M' (whole millions) or '⟪N⟫K' (sub-million)."""
    millions = usd / 1e6
    if millions >= 1:
        return f"${int(round(millions))}M"
    return f"${int(round(usd / 1e3))}K"


def _format_usd_equivalent_rounded(usd: float) -> str:
    """Format a USD value with 3 significant digits for bare-magnitude (issue
    #206) RMB amounts — ``≈$1.43M`` (千万元@7.0) / ``≈$14.3M`` (亿元@7.0).

    The whole-millions ``_format_usd_equivalent`` is intentionally kept for
    digit-led amounts (``30亿元`` → ``≈$429M``) so the existing #203 exact
    assertions hold; textual Chinese-numeral amounts resolve to values like
    1.43 or 14.3 million where whole-millions rounding would erase the
    magnitude (1.43 → ``$1M``), so they use this 3-significant-figure form.
    """
    millions = usd / 1e6
    if millions >= 100:
        digits = 0
    elif millions >= 10:
        digits = 1
    else:
        digits = 2
    return f"${millions:.{digits}f}M"


def _annotate_rmb_usd(text: str, rate: float) -> str:
    """Append a canonical USD equivalent next to each RMB-denominated amount.

    ``30亿元`` → ``30亿元（≈$429M @7.0）``; ``50亿元`` → ``50亿元（≈$714M @7.0）``.
    value = amount_yi * 1e8 / rate (or * 1e4 for 万元), shown as whole
    millions.  A non-positive *rate* (or ``None``) disables annotation.

    Issue #206 also covers Chinese-NUMERAL amounts without leading digits:
    a bare ``千万元`` (超/近/约/逾 千万元 → 10,000,000 yuan) → ``≈$1.43M @7.0``
    and a bare ``亿元`` (超/近/约/逾 亿元 → 100,000,000 yuan) → ``≈$14.3M
    @7.0``.  Ambiguous ``数X`` forms (数千万元 / 数亿元) are skipped — they have
    no reliable base.
    """
    if not text or not rate or rate <= 0:
        return text

    def _annotate(match: re.Match[str]) -> str:
        raw = match.group(1).replace(",", "")
        amount = float(raw)
        unit = match.group(2)
        base = 1e8 if unit.startswith("亿") else 1e4
        usd = amount * base / rate
        return f"{match.group(0)}（≈{_format_usd_equivalent(usd)} @{rate:.1f}）"

    def _annotate_textual(match: re.Match[str]) -> str:
        usd = _TEXTUAL_RMB_BASE[match.group(0)] / rate
        return f"{match.group(0)}（≈{_format_usd_equivalent_rounded(usd)} @{rate:.1f}）"

    out = _RMB_YI_RE.sub(_annotate, text)
    out = _RMB_WAN_RE.sub(_annotate, out)
    out = _RMB_TEXTUAL_RE.sub(_annotate_textual, out)
    return out


def _digest_entry_text(entry: dict[str, Any], rate: float) -> tuple[str, str]:
    """Return (title, summary) with canonical RMB→USD annotations applied."""
    title = str(entry.get("title", "") or "")
    summary = str(entry.get("summary", "") or "")
    return _annotate_rmb_usd(title, rate), _annotate_rmb_usd(summary, rate)


def _build_digest_llm_prompt(
    entries: list[dict[str, Any]],
    product_family: str = "digest",
    rmb_usd_rate: float | None = None,
) -> str:
    """Build the user prompt for LLM digest synthesis.

    For product template families (``premium-briefing`` /
    ``enterprise-briefing`` / ``magazine-digest``) the requested field set
    additionally includes the §2.4 product fields — ``implications`` /
    ``risks`` / ``action_required`` (index-aligned with ``key_findings``),
    plus ``key_metrics`` for enterprise-briefing — keyed by the resolved
    family. The default ``digest`` family is unchanged (spec §2.4, todo 7).

    *rmb_usd_rate* (config-driven, issue #203) injects the canonical USD
    equivalent next to RMB-denominated amounts; ``None`` reads it from config.
    """
    if rmb_usd_rate is None:
        rmb_usd_rate = _get_rmb_usd_rate()
    lines: list[str] = [
        "Synthesize the following knowledge base entries into a digest.",
        "",
    ]

    for i, entry in enumerate(entries, 1):
        title, summary = _digest_entry_text(entry, rmb_usd_rate)
        tags_raw = entry.get("tags", "")
        if isinstance(tags_raw, str):
            try:
                tags_list = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                tags_list = [tags_raw] if tags_raw else []
        elif isinstance(tags_raw, list):
            tags_list = tags_raw
        else:
            tags_list = []
        tags_str = ", ".join(tags_list) if tags_list else "\u2014"

        lines.append(f"Entry {i}:")
        lines.append(f"  Title: {title or '(no title)'}")
        lines.append(f"  Summary: {summary[:500] if summary else chr(8212)}")
        lines.append(f"  Tags: {tags_str}")
        lines.append(f"  Source URL: {entry.get('source_url') or chr(8212)}")
        lines.append("")

    lines.append("Now generate a JSON digest with the following fields:")
    for desc in _DIGEST_FIELD_DESCRIPTIONS:
        lines.append(f"  - {desc}")
    product_descs = _DIGEST_PRODUCT_FIELD_DESCRIPTIONS.get(product_family, [])
    if product_descs:
        lines.append("")
        lines.append("Additional product fields:")
        for desc in product_descs:
            lines.append(f"  - {desc}")
    lines.append("")
    lines.append(
        "When a key finding, recommendation, or trend is backed by a "
        "specific entry, cite its source inline as (Source: URL)."
    )
    # Issue #140: differentiate premium vs enterprise briefing scope so the
    # two paid products read as distinct angles rather than the same content
    # in a different layout.  The directive is prompt-level (no field or
    # context split) so both families keep the same data contract.
    scope_guidance = _DIGEST_PRODUCT_SCOPE_GUIDANCE.get(product_family)
    if scope_guidance:
        lines.append("")
        lines.append(scope_guidance)
    # Issue #179: hard no-fabrication constraint — content must come ONLY
    # from the entries.  Info-poor entries otherwise invite the model to
    # invent teams/motives/numbers/directions (P0-3/P0-4).  Canonical string
    # lives in quality_constraints (#194 spec D).
    lines.append("")
    lines.append(NO_FABRICATION_CONSTRAINT)
    # Issue #200: never rename/abstract source signals into new terms
    # ("low market breadth" must not replace "low VIX, inflation shocks,
    # and excessive AI spending").  Canonical string in quality_constraints.
    lines.append("")
    lines.append(SYNTHESIS_SIGNAL_TRACEABILITY_CONSTRAINT)
    # Issue #445: name the failure mode the AC5 review found — the synthesis
    # introducing an entity no supplied entry mentions, or attaching a claim
    # to an unrelated source.  Canonical string in quality_constraints; the
    # deterministic backstop is _ground_synthesis_citations.
    lines.append("")
    lines.append(SYNTHESIS_ENTITY_GROUNDING_CONSTRAINT)
    # Issue #207: every (Source: URL) must be taken VERBATIM from the KB
    # Entries list above — never re-slug or invent a URL (mirror of the
    # presentation prompt's #93 wording).  Canonical string in quality_constraints.
    lines.append("")
    lines.append(URL_VERBATIM_CONSTRAINT)
    lines.append("Return all fields in a single JSON object.")

    return "\n".join(lines)


def _call_llm_for_digest(
    prompt: str,
    config: Config | None = None,
    *,
    max_synthesis_attempts: int = 2,
    retry_backoff_seconds: float = 0.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Call LiteLLM to synthesize a digest from entries.

    Uses the same LiteLLM pattern as :class:`LLMExtractor` but with
    a custom summarization prompt.

    *max_synthesis_attempts* bounds the retry loop (default 2 — the historical
    "#217 retry once" behaviour for direct callers).  ``generate_digest``
    forwards its own public knobs here so a caller can collapse the budget to
    a single attempt (e.g. when the LLM prerequisite is provably absent) and
    *retry_backoff_seconds* is slept via *sleep_fn* between attempts.
    """
    from autoinfo.output import fault_inject  # noqa: PLC0415

    try:
        fault_inject.maybe_fault("digest")
    except Exception as exc:
        logger.warning("FAULT_INJECT[digest]: %s", exc)
        return {}

    if config is None:
        config_path = get_config_path()
        if config_path is not None:
            try:
                config = load_config(config_path) or Config()
            except Exception:
                config = Config()
        else:
            config = Config()

    model = config.llm.resolve_model()
    full_model = model

    # Issue #217: DeepSeek-V4-Flash intermittently returns empty synthesis on
    # long prompts (empty content / unparseable JSON).  Retry once — a
    # probabilistic empty output usually succeeds on the second attempt —
    # before giving up and returning an empty dict (which the caller then
    # fills deterministically from the real entries).  The bound and the
    # inter-attempt sleep are injectable (T17), defaulting to the historical
    # 2-attempt / no-sleep behaviour.
    attempts = max(1, max_synthesis_attempts)
    last: dict[str, Any] = {}
    for _attempt in range(attempts):
        if _attempt > 0:
            sleep_fn(retry_backoff_seconds)
        try:
            response = call_with_fallback(
                model=full_model,
                messages=[
                    {"role": "system", "content": _DIGEST_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                json_mode=config.llm.json_mode and not config.llm.reasoning_model,
                max_tokens=8000,
                temperature=0.1,
                api_key=config.llm.api_key or None,
                base_url=config.llm.base_url or None,
            )
        except Exception as exc:
            logger.error("LLM digest synthesis failed: %s", exc)
            break

        content: str = response.choices[0].message.content or ""
        content = fault_inject.maybe_fault_content("digest", content)
        parsed = _parse_json_response(content)
        if parsed:
            return parsed
        last = parsed
        logger.warning(
            "LLM digest synthesis returned empty/missing fields (attempt %d/%d) — retrying",
            _attempt + 1,
            attempts,
        )

    return last


def _parse_json_response(content: str | None) -> dict[str, Any]:
    """Parse a JSON string with fallback strategies.

    1. Direct :func:`json.loads`.
    2. Extract JSON from markdown code blocks.
    3. Find the first ``{…}`` brace-delimited block.
    """
    import re  # noqa: PLC0415

    if content is None:
        logger.warning("LLM returned None content — possible json_object mode mismatch")
        return {}

    # Strategy 1 — direct
    try:
        return cast(dict[str, Any], json.loads(content))
    except json.JSONDecodeError:
        pass

    # Strategy 2 — fenced code block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if match:
        try:
            return cast(dict[str, Any], json.loads(match.group(1)))
        except json.JSONDecodeError:
            pass

    # Strategy 3 — bare JSON object
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return cast(dict[str, Any], json.loads(match.group(0)))
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse LLM digest response as JSON: %.200s", content)
    return {}


# ---------------------------------------------------------------------------
# Deterministic synthesis fallback (issue #217)
# ---------------------------------------------------------------------------


def _deterministic_synthesis_fallback(
    entries: list[dict[str, Any]],
    summary_prefix: str = "This digest covers",
) -> dict[str, Any]:
    """Build non-empty D1-required synthesis sections from real entries.

    Issue #217: DeepSeek-V4-Flash intermittently returns empty/missing
    synthesis fields (long prompts, empty content).  When the LLM path
    still yields nothing after the bounded retry, D1 would block the
    product for empty ``key_findings`` / ``summary`` / ``recommendations``.
    This derives those sections from the actual entry titles and summaries
    — real content, never fabricated — so the product stays complete and
    D1 passes.

    Parameters
    ----------
    entries:
        KB entry dicts used to produce the output.  Each carries at least
        ``title`` and optionally ``summary``.
    summary_prefix:
        Leading phrase for the generated executive summary (defaults to a
        digest-style phrase; reports pass ``"This report covers"``).

    Returns
    -------
    dict
        ``{"executive_summary": str, "key_findings": list[str | dict],
        "recommendations": list[str]}`` with all sections non-empty when
        entries exist.  Findings for entries that carry a ``source_url``
        are ``{"text": str, "source_url": str}`` objects (issue #279) so
        rendered output can cite per-finding provenance; entries without
        a URL keep the legacy ``"title: summary"`` string form.
    """
    titled = [e for e in entries if (e.get("title") or "").strip()]
    if not titled:
        return {
            "executive_summary": "No knowledge base entries were available.",
            "key_findings": [],
            "recommendations": [],
        }

    title_line = ", ".join(str(e["title"]).strip() for e in titled[:8])
    executive_summary = f"{summary_prefix} the latest developments this period: {title_line}."
    key_findings: list[Any] = []
    for e in titled[:8]:
        text = f"{str(e['title']).strip()}: {str(e.get('summary') or e['title']).strip()}"
        src = str(e.get("source_url") or "").strip()
        key_findings.append({"text": text, "source_url": src} if src else text)
    recommendations = [
        f"Review the {len(titled)} knowledge base entr"
        f"{'y' if len(titled) == 1 else 'ies'} listed above for follow-up."
    ]
    return {
        "executive_summary": executive_summary,
        "key_findings": key_findings,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Source attribution (F46)
# ---------------------------------------------------------------------------


def _get_domain_source_configs(domain: str) -> list["SourceConfig"]:
    """Load SourceConfig objects for *domain* from the project config.

    Returns an empty list when the config cannot be loaded or the domain
    is not found.
    """
    config_path = get_config_path()
    if config_path is None or not config_path.is_file():
        return []
    try:
        config = load_config(config_path)
    except Exception:
        return []
    for d in config.domains:
        if d.name == domain:
            return list(d.sources)
    return []


# Generic source_platform values that carry no specific source identity (the
# #325 re-derivation replaces these with the configured source name when a
# hostname match can be made against the domain's source configs).

# SourceConfig types whose entries can be matched to a source by hostname.


def _build_attribution_footer(
    sources: list["SourceConfig"],
    output_format: str = "markdown",
) -> str:
    """Build a source attribution section for generated outputs.

    Deduplicates by URL.  Each source is formatted as::

        Source: **{name}** ({url}) — Tier {quality_tier}, {tos_classification}

    Parameters
    ----------
    sources : list[SourceConfig]
        Source configurations to attribute.  Deduplicated by URL before
        rendering.
    output_format : str
        Output format: ``"markdown"`` (default), ``"html"``, or ``"json"``.

    Returns
    -------
    str
        Formatted attribution string.  Empty string when *sources* is
        empty or contains no valid URLs.
    """
    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[SourceConfig] = []
    for s in sources:
        url = (s.url or "").strip().rstrip("/")
        if url and url not in seen:
            seen.add(url)
            unique.append(s)

    if not unique:
        return ""

    if output_format == "json":
        return json.dumps(
            [
                {
                    "name": s.name,
                    "url": s.url,
                    "quality_tier": s.quality_tier,
                    "tos_classification": s.tos_classification,
                }
                for s in unique
            ],
            indent=2,
            ensure_ascii=False,
        )

    lines: list[str] = []
    for s in unique:
        lines.append(f"- **{s.name}** ({s.url}) — Tier {s.quality_tier}, {s.tos_classification}")
    body = "\n".join(lines)

    if output_format == "html":
        escaped_lines = "\n".join(
            "    <li>"
            + html.escape(f"{s.name} ({s.url}) — Tier {s.quality_tier}, {s.tos_classification}")
            + "</li>"
            for s in unique
        )
        return (
            '<footer class="source-attribution">\n'
            f"  <h2>Source Attribution</h2>\n"
            f"  <ul>\n{escaped_lines}\n  </ul>\n"
            f"</footer>"
        )

    # Default: markdown
    return f"---\n\n## Source Attribution\n\n{body}\n"


def _normalize_column_sections(raw: Any) -> list[dict[str, Any]]:
    """Normalize the LLM ``sections`` array to ``{title, content, entries}``.

    Drops items without a usable ``title`` or ``content`` so the column
    template never renders empty subsections (issue #316).  ``entries`` is
    carried through when the LLM provides it (optional — the template
    renders an entry table only when present).
    """
    if not isinstance(raw, list):
        return []
    sections: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        if not title or not content:
            continue
        section: dict[str, Any] = {"title": title, "content": content}
        entries = item.get("entries")
        if isinstance(entries, list):
            section["entries"] = entries
        sections.append(section)
    return sections


def _deterministic_column_sections(
    entries: list[dict[str, Any]], domain: str = ""
) -> list[dict[str, Any]]:
    """Derive column deep-dive sections deterministically from entries (#316).

    Groups entries by theme (source_type → domain → keyword, the same
    deterministic fallback the report path uses) and emits one section per
    group; when the grouping yields fewer than 8 sections but there are at
    least 8 entries, falls back to one section per entry (title + summary)
    so the column Deep Dive never renders the empty placeholder when
    entries exist.
    """
    groups = _deterministic_grouping(entries, domain=domain)
    if groups:
        sections = [
            {
                "title": str(g.get("theme") or "").strip(),
                "content": str(g.get("description") or "").strip(),
                "entries": list(g.get("entries") or []),
            }
            for g in groups
            if (str(g.get("theme") or "").strip())
        ]
        if len(sections) >= 8:
            return sections
    # One section per entry (title + summary) — real content, never
    # fabricated, and never an empty Deep Dive when entries exist.
    _log_grouping_degraded(
        "entry_level",
        "entry_level",
        f"deterministic column sections fell back to one section per entry "
        f"({len(entries)} sections) — <8 theme sections were derivable",
    )
    sections = []
    for e in entries:
        title = str(e.get("title") or "").strip()
        if not title:
            continue
        summary = str(e.get("summary") or "").strip()
        sections.append(
            {
                "title": title,
                "content": summary or title,
                "entries": [e],
            }
        )
    return sections


def _deterministic_takeaway_fields(
    entries: list[dict[str, Any]],
    domain: str = "",
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    """Derive premium-briefing per-takeaway implication / risk / action
    deterministically from real entries (issue #329).

    Mirrors :func:`_deterministic_column_sections`: when the LLM synthesis
    carries no (or too few) per-takeaway implication/risk/action entries,
    derive them one-per-ranked-entry from the actual KB entries so the
    premium template never renders the ``_No ..._`` empty-state placeholders.

    Issue #54 (paid review): the fallback must be HONEST, never impersonate
    real analysis.  Pre-#54 it fabricated ``Uncertain trajectory for …`` +
    ``likelihood medium / impact medium`` for every entry — indistinguishable
    from genuine LLM risk analysis and a value inversion against enterprise.
    The fallback now states plainly that NO differentiated signal was captured
    this period and rates likelihood/impact as ``n/a`` (nothing fabricated).

    Returns ``(implications, risks, action_required)`` — index-aligned lists
    (one item per entry) in the same shape the premium-briefing template
    reads.
    """
    ranked = sorted(
        (e for e in entries if isinstance(e, dict)),
        key=lambda e: float(e.get("relevance_score") or 0.0),
        reverse=True,
    )
    implications: list[str] = []
    risks: list[dict[str, Any]] = []
    action_required: list[str] = []
    for e in ranked:
        title = str(e.get("title") or "this topic").strip()
        if not title:
            continue
        url = str(e.get("source_url") or "").strip()
        implications.append(
            f"No differentiated signal captured for {title} this period — "
            "revisit next period for follow-up developments."
        )
        risks.append(
            {
                "title": "No differentiated risk signal this period — revisit next period.",
                "likelihood": "n/a",
                "impact": "n/a",
                "mitigation": (
                    "Revisit next period and validate against additional sources before rating."
                ),
            }
        )
        action_required.append(
            f"Revisit {title} ({url}) next period for a differentiated assessment."
        )
    return implications, risks, action_required


def _fill_premium_takeaway_fields(
    implications: list[Any] | None,
    risks: list[dict[str, Any]] | None,
    action_required: list[str] | None,
    entries: list[dict[str, Any]],
    domain: str,
    *,
    weak: bool = False,
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    """#357 — the premium per-takeaway slots must never render empty or
    ``_No ..._`` placeholder text.  A slot list that is missing/empty is
    filled with the full deterministic fallback; a non-empty list has its
    empty/placeholder-shaped elements replaced per-index.  The list length
    the LLM produced is preserved (no padding) so product-analysis
    persistence stays faithful to the raw synthesis.

    #10 — the opt-in *weak* predicate (default False keeps the ``_usable``
    behavior) additionally replaces weak-but-non-empty action lines: a bare
    verb phrase like ``"Track AI model releases"`` (no concrete object, no
    timeframe/trigger) is flagged by :func:`autoinfo.validation_matrix._is_weak_analysis`
    and swapped per-index for the KB-derived deterministic action, so the
    premium render ships WHAT/WHEN-shaped actions even when the LLM falls
    back to shallow phrasing.  Scope: PREMIUM-ONLY — the enterprise
    ``action_required`` is a flat ``- [ ]`` checkbox list whose shape
    ``_so_what_substantive`` requires, so enterprise callers never pass
    ``weak=True`` (their lever is the prompt-side WHAT/WHEN constraint).

    The validation_matrix import is FUNCTION-LOCAL because
    ``validation_matrix`` imports ``from autoinfo.output import …`` at
    function scope (lines 124/1044/1084 of that module) — a module-level
    ``output → validation_matrix`` import would be a hard cycle.
    """
    from autoinfo.validation_matrix import _is_weak_analysis  # noqa: PLC0415

    _impl, _risks, _actions = _deterministic_takeaway_fields(entries, domain)

    def _usable(value: Any) -> bool:
        if isinstance(value, dict):
            return _usable(value.get("title"))
        if not isinstance(value, str):
            return False
        stripped = value.strip()
        return bool(stripped) and not _is_empty_placeholder(stripped)

    def _is_weak(value: Any) -> bool:
        """Weak when unusable, or (with *weak* enabled) a weak-shaped action."""
        if not _usable(value):
            return True
        if not weak:
            return False
        if isinstance(value, dict):
            return _is_weak_analysis(str(value.get("title") or ""))
        return _is_weak_analysis(str(value))

    def _fill(
        values: list[Any] | None,
        fallback: list[Any],
        is_dict: bool = False,
    ) -> list[Any]:
        values = list(values) if values else []
        if not values:
            return [dict(v) for v in fallback] if is_dict else list(fallback)
        if is_dict:
            return [
                dict(v) if isinstance(v, dict) and not _is_weak(v) else dict(fallback[i])
                for i, v in enumerate(values[: len(fallback)])
            ]
        return [
            (str(v).strip() if not _is_weak(v) else fallback[i])
            for i, v in enumerate(values[: len(fallback)])
        ]

    return (
        _fill(implications, _impl),
        _fill(risks, _risks, is_dict=True),
        _fill(action_required, _actions),
    )


# --- #445 synthesis citation grounding --------------------------------------
#
# The AC5 review found products that attach a claim to an unrelated source:
# an English-learning product attributing statements about Duolingo and
# enterprise rollouts to "A guide to 6th grade math topics".  The synthesis
# prompt now says so (``SYNTHESIS_ENTITY_GROUNDING_CONSTRAINT``), and this is
# the deterministic backstop: a synthesis sentence that cites a supplied
# entry's URL while describing something that entry never mentions is removed
# before it can reach a template.
#
# Precision model — deliberately narrow, because a wrong drop silently edits
# an honest summary:
#
# * Only sentences carrying a resolvable ``(Source: <url>)`` citation are
#   considered; with no citation there is nothing to verify against.
# * The cited URL must match a supplied entry, otherwise the sentence passes
#   (an unresolvable citation is #207's URL problem, already gated elsewhere).
# * A sentence is dropped only when a large majority of its distinctive
#   content words are absent from that entry's own title/summary/content/tags
#   AND at least four such words are missing.  Word overlap, not entity
#   matching, is the test: it cannot mis-fire on a legitimate paraphrase.
# * Honest hedges pass, per the #179/#191 invariant.

_MISSING_SHARE_THRESHOLD = 0.6
_MIN_MISSING_DISTINCTIVE_WORDS = 4
_DISTINCTIVE_WORD_MIN_LEN = 5
_CITED_URL_RE = re.compile(r"\(Sources?:\s*([^)]+)\)", re.IGNORECASE)
_URL_IN_TEXT_RE = re.compile(r"https?://[^\s)\]]+")


def _distinctive_words(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z][a-z0-9'\-]+", text.lower())
        if len(word) >= _DISTINCTIVE_WORD_MIN_LEN
    }


def _entry_text_by_url(entries: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("source_url") or "").strip()
        if url:
            result.setdefault(url, grounding_corpus([entry]))
    return result


def _ground_synthesis_citations(
    text: str,
    entries: list[dict[str, Any]],
) -> str:
    """Drop synthesis sentences whose citation does not support them (#445).

    Returns *text* unchanged when it is not cited prose, when no cited URL
    resolves to a supplied entry, or when the cited entry's own text overlaps
    the sentence enough to be a plausible paraphrase.
    """
    if "(source" not in text.lower():
        return text
    by_url = _entry_text_by_url(entries)
    if not by_url:
        return text
    kept: list[str] = []
    for sentence in split_sentences(text):
        if HONEST_HEDGE_RE.search(sentence):
            kept.append(sentence)
            continue
        citation = _CITED_URL_RE.search(sentence)
        cited = (
            [u for u in _URL_IN_TEXT_RE.findall(citation.group(1)) if u in by_url]
            if citation
            else []
        )
        if not cited:
            kept.append(sentence)
            continue
        words = _distinctive_words(_URL_IN_TEXT_RE.sub(" ", _CITED_URL_RE.sub(" ", sentence)))
        if len(words) < _MIN_MISSING_DISTINCTIVE_WORDS:
            kept.append(sentence)
            continue
        corpus = set(_distinctive_words(" ".join(by_url[u] for u in cited)))
        missing = words - corpus
        if (
            len(missing) >= _MIN_MISSING_DISTINCTIVE_WORDS
            and len(missing) / len(words) >= _MISSING_SHARE_THRESHOLD
        ):
            _log_grounding_drop(sentence, sorted(missing)[:5])
            continue
        kept.append(sentence)
    return " ".join(kept).strip()


def _log_grounding_drop(sentence: str, missing: list[str]) -> None:
    logger.warning(
        "Synthesis grounding (#445): dropped a cited sentence whose source does "
        "not support it (unsupported terms: %s): ...%s...",
        ", ".join(missing),
        sentence[:120],
    )


def _normalize_digest_product_context(
    context: dict[str, Any],
    domain: str,
    product_family: str = "digest",
    ref_limit: int | None = None,
) -> dict[str, Any]:
    """Normalize the digest context to the flat §2.1 product-template shape.

    The digest path renders product templates with a context that nests the
    LLM synthesis under ``llm_synthesis``; product templates
    (``premium-briefing`` / ``enterprise-briefing`` / ``magazine-digest``)
    read only the FLAT keys pinned by ``phaseA-template-spec.md`` §2.1 —
    the same shape the report path produces via :func:`_report_data_to_dict`.
    This flattens the digest context to that dual-context contract:

    - ``executive_summary`` ← ``llm_synthesis["executive_summary"]``
      (``""`` when absent)
    - ``key_findings`` ← ``llm_synthesis["key_findings"]`` converted to
      ``list[dict]`` of ``{"text", "source_url"}`` (LLM ``{topic, detail}``
      dicts become ``"topic: detail"`` text; partial items kept, empty
      items dropped; ``source_url`` kept when the LLM provides it and
      back-filled from the entry list on an unambiguous title match —
      issue #279)
    - ``recommendations`` ← ``llm_synthesis["recommendations"]``
    - ``references`` ← derived from ``entries`` with the report-path item
      shape ``{title, source_url, source_type, source_platform, domain}``
      (spec §2.3 rule 4; ``entry.get("domain", <domain>)`` fallback)
    - product-specific fields (todo 7): ``implications``, ``risks``,
      ``action_required``, ``key_metrics`` ← flattened from
      ``llm_synthesis`` when present, else ``[]`` — generic, so any new
      synthesis field flows through automatically
    - ``sections`` (issue #316): the column template's Deep Dive source —
      flattened from ``llm_synthesis["sections"]`` when present (list of
      ``{title, content, entries}`` dicts, unusable items dropped); when
      *product_family* is ``"column"`` and no usable sections exist but
      entries do, sections are derived deterministically from the entries
      so the template never renders the empty placeholder.  Non-column
      families default to ``[]`` (backward compatible).

    All other top-level digest keys (``title``, ``domain``, ``generated_at``,
    ``period``, ``entries``, …) are kept untouched — templates must simply
    not read them (spec §2.3 rule 6).
    """
    synthesis_raw = context.get("llm_synthesis")
    synthesis = synthesis_raw if isinstance(synthesis_raw, dict) else {}
    raw_entries = context.get("entries")
    entries_list = raw_entries if isinstance(raw_entries, list) else []

    # --- Flattened top-level keys ------------------------------------------
    flat: dict[str, Any] = dict(context)
    flat["executive_summary"] = str(synthesis.get("executive_summary") or "")

    raw_findings = synthesis.get("key_findings", [])
    findings: list[dict[str, Any]] = []
    if isinstance(raw_findings, list):
        for item in raw_findings:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    findings.append({"text": text})
                continue
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic") or "").strip()
            detail = str(item.get("detail") or "").strip()
            if topic and detail:
                text = f"{topic}: {detail}"
            elif topic:
                text = topic
            elif detail:
                text = detail
            elif item.get("text"):
                text = str(item["text"]).strip()
            else:
                continue
            # Issue #148: strip LLM-echoed internal "Entry N" references from
            # key-finding text before it reaches the template.
            finding: dict[str, Any] = {"text": _strip_entry_refs(text)}
            src = str(item.get("source_url") or "").strip()
            if src:
                finding["source_url"] = src
            findings.append(finding)
    # Issue #279: back-fill source_url from entries on an unambiguous
    # title match only (wrong attribution is worse than none).
    for finding in findings:
        if finding.get("source_url"):
            continue
        text = str(finding.get("text") or "").strip().lower()
        if not text:
            continue
        tokens = [t for t in re.split(r"[^a-z0-9]+", text.split(":")[0]) if t]
        if len(tokens) < 2:
            continue
        matches = [
            e.get("source_url")
            for e in entries_list
            if isinstance(e, dict)
            and (e.get("source_url") or "").strip()
            and all(t in str(e.get("title") or "").lower() for t in tokens)
        ]
        if len(matches) == 1:
            finding["source_url"] = str(matches[0]).strip()
    flat["key_findings"] = findings

    raw_recommendations = synthesis.get("recommendations", [])
    flat["recommendations"] = (
        [_strip_entry_refs(str(r)) for r in raw_recommendations]
        if isinstance(raw_recommendations, list)
        else []
    )

    # --- References derived from entries (report-path item shape) ----------
    # #325: derive the specific source label for entries whose stored
    # source_platform is a generic placeholder (pre-#323 'rss' etc.).
    # #11: cap at ref_limit, sorted by (has summary, relevance) desc — the
    # sort MUST run on the entries BEFORE the ref dicts drop summary/relevance.
    _ref_limit = ref_limit if ref_limit is not None else _output_config_ref_limit()
    _src_configs = _get_domain_source_configs(domain)
    flat["references"] = []
    for e in _sorted_ref_entries([e for e in entries_list if isinstance(e, dict)], domain=domain)[
        :_ref_limit
    ]:
        _label = _derive_source_label(
            e,
            e.get("domain", domain),
            source_configs=_src_configs,
        )
        flat["references"].append(
            {
                "title": e.get("title", ""),
                "source_url": e.get("source_url", ""),
                "source_type": e.get("source_type", ""),
                "source_platform": _label,
                "domain": e.get("domain", domain),
                "description": (
                    str(e.get("summary") or "").strip()
                    or str(e.get("content") or "")[:120].strip()
                    or f"{_label} item"
                ),
            }
        )

    # --- Enterprise/premium key_findings cap (issue #11, decision a) ------
    # The enterprise-briefing template renders the selection-scope label
    # ``selected {{ key_findings|length }} of {{ references|length }}``.  Cap
    # the findings to min(12, len(references)) for the premium/enterprise
    # families so a ref_limit below the findings count can never invert the
    # label (``selected 9 of 8``).
    if product_family in ("premium-briefing", "enterprise-briefing"):
        flat["key_findings"] = _cap_product_key_findings(flat["key_findings"], flat["references"])

    # --- Product-specific fields (todo 7), flattened generically ----------
    # List-shaped fields flow through as-is; string-shaped editorial fields
    # (editorial_intro / feature_story, issue #313) carry through as strings.
    for synthesis_field in (
        "implications",
        "risks",
        "action_required",
        "key_metrics",
        "editorial_intro",
        "feature_story",
    ):
        value = synthesis.get(synthesis_field, [])
        flat[synthesis_field] = (
            value if isinstance(value, list) else (str(value) if isinstance(value, str) else [])
        )

    # --- Deterministic per-takeaway fields (issue #329) --------------------
    # premium-briefing's takeaway layer renders per-takeaway implication /
    # risk / action by index-aligning with key_findings.  When the LLM
    # synthesis carries none (or fewer than the takeaways) OR slot values that
    # are empty / `_No ..._` placeholder-shaped, the template's `{% else %}`
    # empty-state renders `_No ..._` placeholders.  Backfill each slot
    # per-index with the deterministic fallback derived from the real entries
    # so the premium product never ships a hollow Action/Risk/So-what (same
    # pattern as #316/#326 column sections; placeholder-element case #357).
    if product_family == "premium-briefing" and entries_list:
        flat["implications"], flat["risks"], flat["action_required"] = (
            _fill_premium_takeaway_fields(
                flat.get("implications"),
                flat.get("risks"),
                flat.get("action_required"),
                entries_list,
                domain,
            )
        )

    # --- Column deep-dive sections (issue #316) ---------------------------
    # The column template renders ``sections`` (list of {title, content,
    # entries}) for the Deep Dive + Implications sections.  Flatten the LLM
    # synthesis ``sections`` array when present; when the family is column
    # and no usable sections exist but entries do, derive them
    # deterministically so the template never renders the empty placeholder.
    sections = _normalize_column_sections(synthesis.get("sections"))
    if product_family in ("column", "report") and not sections and entries_list:
        # #326: derive sections deterministically for the report family too
        # (previously only "column" got a deterministic fallback, so the
        # report product rendered `**Sections**: 0` + an empty shell whenever
        # the LLM synthesis carried no explicit sections).
        sections = _deterministic_column_sections(entries_list, domain)
        if product_family == "column" and len(sections) > 1:
            # #120 (C4): entry-level column sections are BY DESIGN, but they
            # are a degraded (non-semantic) grouping — the rendered Deep Dive
            # must carry the honest "grouped by source" marker so readers
            # never mistake one-section-per-entry for semantic topics.
            sections = [
                {
                    "marker": _grouping_degradation_marker("entry_level"),
                }
            ] + sections
    flat["sections"] = sections

    # --- Tutorial sections (issue #342) -----------------------------------
    # The digest path renders the tutorial template (the matrix generates
    # tutorial via generate_digest with the tutorial template).  The flat
    # context carries no objectives/content/exercises/further_reading keys,
    # so the template's ``{% else %}`` branches render ``_No objectives
    # defined._`` / ``_No exercises provided._`` / ``_No references
    # provided._``.  Fill them from the real entries via the same
    # ``_entry_derived_sections`` helper the real ``generate_tutorial``
    # uses; when there are no entries, leave them empty and let the
    # template's neutral prose render (never a placeholder).
    if product_family == "tutorial":
        if entries_list:
            _objectives, _content, _exercises, _further = _entry_derived_sections(entries_list)
        else:
            _objectives, _content, _exercises, _further = [], [], [], []
        flat.setdefault("objectives", _objectives)
        flat.setdefault("content", _content)
        flat.setdefault("exercises", _exercises)
        flat.setdefault("further_reading", _further)
        # Issue #99: the digest-path tutorial (``--product tutorial``) renders
        # the same header fields as ``generate_tutorial`` (#92 fills them via
        # ``_ensure_tutorial_complete``).  This flat context carries no
        # audience/duration/prerequisites/summary, so a "Weekly Tutorial"
        # would ship an empty header + empty Summary.  Fill them with the
        # same deterministic defaults #92 uses on the generate_tutorial path.
        audience = str(flat.get("target_audience") or "").strip()
        if not audience:
            audience = "general audience"
        flat["target_audience"] = audience
        raw_duration = str(flat.get("duration") or "").strip()
        if raw_duration.lower() in ("tbd", "none", "0 minutes", "", "n/a"):
            flat["duration"] = f"{len(entries_list)} minutes"
        raw_prereq = str(flat.get("prerequisites") or "").strip()
        if raw_prereq.lower() in ("tbd", "none", "", "n/a"):
            flat["prerequisites"] = "None (no prior experience required)"
        if not str(flat.get("summary") or "").strip():
            # Issue #147: the previous fallback leaked internal counts
            # ("27 knowledge base entries"), the internal KB term, the raw
            # domain slug, and a doubled "audience audience" word.  Use
            # user-facing wording with the display domain name and no count.
            # Note: *audience* already reads "general audience", so do not
            # append another "audience" noun.
            period_word = str(context.get("period_label") or "").lower() or "current"
            flat["summary"] = (
                f"This tutorial covers the key {period_word} findings "
                f"in {_domain_display_name(domain)}, with exercises and a "
                f"summary for {audience}."
            )

    # --- #445: ground the LLM narrative against the supplied entries -------
    # Runs LAST so every deterministic fill above (implications, sections,
    # key_findings) is already in place and is itself a legitimate fallback
    # for anything grounding removes.
    _ground_flat_synthesis(flat, entries_list, product_family)

    return flat


def _ground_flat_synthesis(
    flat: dict[str, Any],
    entries: list[dict[str, Any]],
    product_family: str,
) -> None:
    """Strip unsupported citations from the flat context's narrative (#445).

    Mutates *flat* in place.  ``executive_summary`` falls back to the
    deterministic entry-derived summary ONLY when grounding emptied a summary
    the LLM actually produced; an absent synthesis still yields ``""`` (the
    generation layer, not this one, owns that fallback, and D1 owns the
    "present but empty" verdict).
    """
    if not entries:
        return
    had_summary = bool(str(flat.get("executive_summary") or "").strip())
    for key in ("executive_summary", "editorial_intro", "feature_story"):
        value = flat.get(key)
        if isinstance(value, str) and value.strip():
            flat[key] = _ground_synthesis_citations(value, entries)
    if had_summary and not str(flat.get("executive_summary") or "").strip():
        flat["executive_summary"] = _deterministic_synthesis_fallback(entries)["executive_summary"]
    findings = flat.get("key_findings")
    if isinstance(findings, list):
        for finding in findings:
            if isinstance(finding, dict) and isinstance(finding.get("text"), str):
                finding["text"] = _ground_synthesis_citations(finding["text"], entries)
    sections = flat.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, dict) and isinstance(section.get("content"), str):
                section["content"] = _ground_synthesis_citations(section["content"], entries)
    if product_family != "premium-briefing":
        implications = flat.get("implications")
        if isinstance(implications, list):
            for index, value in enumerate(implications):
                if isinstance(value, str) and value.strip():
                    implications[index] = _ground_synthesis_citations(value, entries)


# ---------------------------------------------------------------------------
# Shared story-set selection (cross-product coherence, #119)
# ---------------------------------------------------------------------------
# SINGLE-DOMAIN products only.  The cross-domain paths (generate_digest's
# per-domain loop, generate_report's cross-domain loop) are NOT routed here.


def _select_story_set(
    store: "KBStore",
    domain: str,
    period: str = "weekly",
    product: str = "digest",
    query_limit: int = 200,
) -> tuple[list[dict[str, Any]], tuple[str, str], bool]:
    """Select the shared week-windowed story set for a SINGLE-domain product.

    Reproduces ``generate_digest``'s current single-domain selection so the
    digest's rendered output is byte-identical after the refactor, while
    presentation and report consume the same set (#119 cross-product
    coherence: one domain → one story set → digest / presentation / report
    reference the same sources).

    Selection contract (single-domain path only):

    1. Window: :func:`_compute_date_range` for *period* — the same-week
       ``(date_from, date_to)`` semantics (``weekly`` = the last 7 days,
       both ISO dates inclusive).
    2. Window query: ``store.list_entries(domain=domain, date_from=date_from,
       limit=query_limit)`` — the default window query the digest runs,
       with ``query_limit`` defaulting to 200 (the digest's built-in cap).
    3. Full-domain fallback: when the period window returns NO entries
       (collectors last ran weeks ago), relax to the full domain set —
       ``store.list_entries(domain=domain, limit=query_limit)`` so the
       product is never an empty shell.
    4. Ordering: :func:`_sorted_ref_entries` (references ordering — has
       summary desc, then relevance desc, issue #11/#42) so the LLM-synthesis
       candidates and the digest render consume the same ordered set.

    The caller applies its own downstream filters on the returned set — the
    digest runs ``_filter_digest_entries`` + drift filter + staleness after
    this helper, and the drift filter runs AFTER the shared set so drifted
    entries are excluded from the digest-identical render.  Report applies
    its own product filters and an ``[:200]`` cap.  Returns
    ``(entries, (date_from, date_to), period_was_empty)`` where
    ``period_was_empty`` is True when the window query (or its relaxed
    full-domain fallback) produced no entries.

    Low-value entries are preserved, not dropped: :func:`_sorted_ref_entries`
    drops promo/obituary/celebrity entries for non-language-learning domains
    with enough clean candidates — but the digest's RENDER keeps them (only
    the synthesis candidates drop them).  The shared set re-attaches any
    dropped entries at the tail so the digest render stays byte-identical.

    Deterministic — no LLM, no side effects beyond ``store.list_entries``.
    """
    date_from, date_to = _compute_date_range(period)
    period_entries = store.list_entries(
        domain=domain,
        date_from=date_from,
        limit=query_limit,
    )
    period_was_empty = not period_entries
    entries = period_entries
    if not entries:
        logger.info(
            "No entries for domain '%s' in period %s..%s — falling back to full domain set",
            domain,
            date_from,
            date_to,
        )
        entries = store.list_entries(
            domain=domain,
            limit=query_limit,
        )
        period_was_empty = not entries
    ordered = _sorted_ref_entries(entries, domain=domain)
    if len(ordered) != len(entries):
        ordered_ids = {id(e) for e in ordered}
        dropped = [e for e in entries if id(e) not in ordered_ids]
        if dropped:
            ordered = ordered + sorted(dropped, key=_ref_sort_key, reverse=True)
    return ordered, (date_from, date_to), period_was_empty


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_digest(
    domain: str,
    period: str = "weekly",
    format: str = "markdown",
    llm_config: Config | None = None,
    custom_instructions: str = "",
    target_audience: str = "",
    include_stale: bool = False,
    recipients: list[str] | None = None,
    product_template: ProductTemplate | None = None,
    product_type: str = "PROCESSED",
    delivery_gate_configs: dict[str, dict[str, Any]] | _DeliveryGatesBypass | None = None,
    user_id: str = "",
    max_items: int = 0,
    domains: list[str] | None = None,
    language: str = "",
    ref_limit: int | None = None,
    *,
    max_synthesis_attempts: int = 2,
    retry_backoff_seconds: float = 0.0,
) -> str | DeliveryOutput:
    """Generate a digest of KB entries for *domain* over the given *period*.

    When *domains* is provided with 2+ entries, entries are aggregated
    from all listed domains for a cross-domain digest.

    Parameters
    ----------
    domain:
        Domain to generate the digest for (e.g. ``"medical-research"``).
    period:
        Digest period.  One of ``"daily"``, ``"weekly"``, ``"monthly"``.
        Defaults to ``"weekly"``.
    format:
        Output format.  One of ``"markdown"``, ``"html"``, ``"json"``,
        ``"agent"``.  The ``"agent"`` format returns JSON-LD
        (``@type: KnowledgeDigest``) optimized for LLM re-consumption.
        Defaults to ``"markdown"``.
    llm_config:
        Optional :class:`Config` override for LLM settings.  When omitted,
        the config is auto-detected from the project directory.
    custom_instructions:
        Optional string of additional instructions to append to the LLM
        generation prompt.  Ignored when empty/absent.
    include_stale:
        When ``True``, include stale entries (below domain freshness
        threshold) in the digest.  Defaults to ``False``, which excludes
        them and logs the count of excluded items.
    recipients:
        Optional list of email recipient addresses for direct delivery.
        When provided, the digest can be sent to these addresses via
        the delivery channel.  Defaults to ``None``.
    product_template:
        Optional :class:`ProductTemplate` instance for template rendering.
        When provided, the digest is rendered through the product template
        system (with domain-specific overrides).  When ``None`` (default),
        the existing direct Jinja2 rendering is used (backward compatible).
    product_type:
        Product type for delivery gate checking.  ``"PROCESSED"`` (default)
        enables D1-D3 checks when *delivery_gate_configs* is provided.
        ``"RAW"`` skips all delivery gates.
    delivery_gate_configs:
        Optional dict of ``{gate_name: config_dict}`` for D1-D3 delivery
        gates.  When provided, D1-D3 are run after rendering and the return
        type changes to :class:`DeliveryOutput`.  When ``None`` (default),
        no gates are run and a plain ``str`` is returned (backward
        compatible).
    user_id:
        Optional user ID.  When non-empty, stored preferences from
        :func:`autoinfo.user_store.get_preferences` are auto-loaded and
        used to set *target_audience*, *format*, and *max_items* if they
        were not explicitly provided.  When empty (default), behavior is
        unchanged and no preferences are loaded.
    max_items:
        Optional maximum number of KB entries to include in the digest.
        Defaults to ``0`` (uses built-in limit of 200).  When *user_id*
        is provided and the user's stored preferences include a
        ``max_items`` key, that value is used instead.
    language:
        Optional ISO-639 language code (``"zh"`` / ``"en"``, case/alias
        tolerant: ``zh_CN``, ``中文``, ``en-US`` all match).  When provided,
        only entries whose detected ``language`` matches are included, so a
        digest never mixes languages (issue #309).  Empty (default) includes
        all languages as before.
    ref_limit:
        Optional maximum number of KB references to include in the rendered
        product.  Defaults to ``output.ref_limit`` from the project config
        (60).  Applied at the digest product-context build
        (:func:`_normalize_digest_product_context`), sorted by (has non-empty
        summary desc, ``relevance_score`` desc) — identical to the report
        path (issue #11).

    Returns
    -------
    str or DeliveryOutput
        Plain ``str`` when *delivery_gate_configs* is ``None`` (default).
        :class:`DeliveryOutput` with gate results when *delivery_gate_configs*
        is provided.

    Raises
    ------
    ValueError
        If *period* is not one of ``"daily"``, ``"weekly"``, ``"monthly"``,
        or if *format* is not one of ``"markdown"``, ``"html"``, ``"json"``,
        ``"agent"``, ``"epub"``, ``"audiobook"``.
    """
    # --- Validate parameters ------------------------------------------------
    if period not in PERIOD_DAYS:
        raise ValueError(
            f"Invalid period '{period}'. Must be one of: {', '.join(sorted(PERIOD_DAYS))}"
        )
    valid_formats = {"markdown", "html", "json", "agent", "audio", "epub", "audiobook"}
    if format not in valid_formats:
        raise ValueError(
            f"Invalid format '{format}'. Must be one of: {', '.join(sorted(valid_formats))}"
        )

    # --- Resolve delivery-gate config (issue #298: default-on in production) --
    # ``None`` resolves from the project config (domain ``delivery_gates`` /
    # global ``delivery_gates``); the ``_DELIVERY_GATES_BYPASS`` sentinel
    # explicitly bypasses.  When resolution yields nothing, the caller keeps
    # getting a plain ``str`` (backward compatible).
    delivery_gate_configs = _resolve_delivery_gate_configs(domain, delivery_gate_configs)

    # --- Free-tier quota gate (todo 12) — named users only; user_id="" (batch) skips

    check_free_tier_generation(
        user_id=user_id, domain=domain, product_type="digest", raise_on_block=True
    )

    # --- Determine cross-domain mode -----------------------------------------
    is_cross_domain_digest: bool = domains is not None and len(domains) >= 2
    if is_cross_domain_digest:
        digest_domains: list[str] = domains  # type: ignore[assignment]
        digest_title_domain: str = "Cross-Domain"
    else:
        digest_domains = [domain]
        digest_title_domain = domain
    # Issue #144: the H1 title must use the user-facing domain name
    # (e.g. "Medical Research"), never the internal slug — but the slug
    # stays for internal product_id / domain keys.
    digest_title_domain_display: str = _domain_display_name(digest_title_domain)

    # --- Auto-load preferences from user profile (G10) -----------------------
    content_preference: str = _resolve_content_preference(user_id)
    if user_id:
        try:
            from autoinfo.user_store import (  # noqa: PLC0415
                get_preferences,
            )

            prefs_result = get_preferences(user_id)
            if "preferences" in prefs_result:
                stored_prefs: dict[str, Any] = prefs_result["preferences"]
                # Auto-set target_audience if not explicitly provided
                if not target_audience and stored_prefs.get("target_audience"):
                    target_audience = str(stored_prefs["target_audience"])
                    logger.debug(
                        "Applied stored target_audience='%s' for user '%s'",
                        target_audience,
                        user_id,
                    )
                # Auto-set format if still at default
                if format == "markdown" and stored_prefs.get("format"):
                    stored_fmt = str(stored_prefs["format"]).lower()
                    if stored_fmt in valid_formats:
                        format = stored_fmt
                        logger.debug(
                            "Applied stored format='%s' for user '%s'",
                            format,
                            user_id,
                        )
                # Auto-set max_items if not explicitly provided
                if max_items == 0 and stored_prefs.get("max_items"):
                    try:
                        max_items = int(stored_prefs["max_items"])
                        if max_items < 1:
                            max_items = 0
                        logger.debug(
                            "Applied stored max_items=%d for user '%s'",
                            max_items,
                            user_id,
                        )
                    except (ValueError, TypeError):
                        pass
        except Exception:
            logger.debug(
                "Failed to load preferences for user '%s'",
                user_id,
                exc_info=True,
            )

    # --- Freemium access gating (G15) ----------------------------------------
    if user_id and product_template is not None:
        product_access = getattr(product_template, "access_level", "free")
        if product_access != "free":
            from autoinfo.billing import check_access  # noqa: PLC0415

            access_result = check_access(user_id, product_access)
            if not access_result["allowed"]:
                period_label = PERIOD_LABELS.get(period, period.capitalize())
                blocked_message = (
                    f"# {period_label} Digest \u2014 {domain}\n\n"
                    f"**{access_result['upgrade_prompt'] or 'Access denied.'}**\n\n"
                    f"_Reason_: {access_result['reason']}\n\n"
                    f"_Access level required_: `{product_access}`\n"
                    f"_Your status_: {access_result['profile_status']} "
                    f"(plan: {access_result['plan']})\n"
                )
                if delivery_gate_configs is not None:
                    return DeliveryOutput(
                        output=blocked_message,
                        gate_results={},
                        delivery_blocked=True,
                        delivery_format=format,
                        warnings=[f"G15 blocked: {access_result['reason']}"],
                    )
                return blocked_message

    reset_llm_provenance()

    # --- Compute date range --------------------------------------------------
    period_label = PERIOD_LABELS.get(period, period.capitalize())

    # --- Query KB entries ----------------------------------------------------
    store = KBStore()
    query_limit = max_items if max_items > 0 else 200

    if is_cross_domain_digest:
        date_from, date_to = _compute_date_range(period)
        entries: list[dict[str, Any]] = []
        per_domain_limit = max(query_limit // len(digest_domains), 10)
        for d in digest_domains:
            domain_entries = store.list_entries(
                domain=d,
                date_from=date_from,
                limit=per_domain_limit,
            )
            for e in domain_entries:
                if "domain" not in e:
                    e["domain"] = d
            entries.extend(domain_entries)
        entries = entries[:query_limit]
        period_was_empty = False
    else:
        # Single-domain story set — shared with presentation/report (#119).
        entries, (date_from, date_to), period_was_empty = _select_story_set(
            store,
            domain,
            period=period,
            product="digest",
            query_limit=query_limit,
        )
        entries = _filter_drifted_entries(entries, domain)

    # --- Archive/deprecated exclusion + test/empty filter + convergence ------
    # Shared chain (see _filter_digest_entries) so the #83 full-domain
    # fallback below runs identical filters over its candidate set.
    entries = _filter_digest_entries(entries)

    # Issue #83: the window query returned rows but they were ALL dropped by
    # the archive/deprecated/test filters — the digest would be an empty
    # shell even though valid out-of-window content exists.  Recover the
    # full-domain set (same relaxation as the zero-row fallback above) and
    # re-run the identical filter chain.  Only non-archived active content
    # survives, so archived/low-quality entries are never resurrected.
    # Single-domain only — the cross-domain path has no window fallback.
    if not entries and not period_was_empty and not is_cross_domain_digest:
        logger.info(
            "In-window entries for domain '%s' all dropped by archive/test "
            "filters — falling back to full domain set",
            domain,
        )
        entries = _filter_digest_entries(
            _filter_drifted_entries(
                store.list_entries(domain=domain, limit=query_limit),
                domain,
            )
        )
        period_was_empty = not entries

    # --- Language filter (issue #309 / #317) --------------------------------
    # When a user requests a specific language (or a domain declares a
    # default_language), drop entries in other languages so a digest/report is
    # internally consistent (no zh/en interleave).  An explicit param wins;
    # otherwise the domain default fills in; cross-domain never auto-picks one.
    effective_language = _resolve_effective_language(
        language, domain, cross_domain=is_cross_domain_digest
    )
    if effective_language:
        filtered_entries, collapsed = _filter_entries_by_language_product_safe(
            entries, effective_language
        )
        if collapsed:
            # Issue #53: the resolved language collapsed the domain's primary
            # corpus (stale seed/config), the safety net already fell back to
            # the unfiltered input and logged — use it as-is.
            entries = filtered_entries
        else:
            if (
                not filtered_entries
                and entries
                and not period_was_empty
                and not is_cross_domain_digest
            ):
                # The period window held entries in OTHER languages while the
                # domain's default-language corpus is fully out-of-window (e.g. a
                # zh domain whose people.cn corpus is dated months ago + fresh en
                # in-window).  Relax the DATE window (keep the language filter) so
                # the digest is never an empty shell (backup-repo #28 evidence).
                logger.info(
                    "No '%s'-language entries in the '%s' window for domain '%s' "
                    "- relaxing the date window, keeping the language filter",
                    effective_language,
                    period,
                    domain,
                )
                relaxed = store.list_entries(domain=domain, limit=query_limit)
                if relaxed:
                    filtered_entries = _filter_entries_by_language(relaxed, effective_language)
            entries = filtered_entries

    # --- Per-domain exclude_keywords filter (issue #319) ---------------------
    # Cross-domain noise guard: drop entries whose title/summary/tags match a
    # keyword on the entry's OWN domain's exclude_keywords blacklist BEFORE LLM
    # synthesis.  Deterministic substring match, no LLM involvement.  No-op for
    # domains with an empty list.
    entries = _filter_entries_by_domain_exclusions(entries, domain)

    # --- Source-label enrichment (issue #325) --------------------------------
    # Derive the specific source name for every entry (stale pre-#323 entries
    # carry source_platform='rss') so ALL render surfaces — markdown entry
    # table, magazine byline/clusters, json/agent formats — show the specific
    # source name instead of the generic "(RSS)" label.  Per-entry own domain
    # for cross-domain products.
    entries = _label_entries(entries, domain)

    # --- Parse tags for each entry (they come as JSON strings from SQLite) ----
    for entry in entries:
        tags_raw = entry.get("tags", "")
        if isinstance(tags_raw, str):
            try:
                entry["tags"] = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                entry["tags"] = [tags_raw] if tags_raw else []
        elif not isinstance(tags_raw, list):
            entry["tags"] = []

    # --- Promotion trigger (T6): promote eligible 02-Draft entries ------------
    # Best-effort per entry: a rejected/failed promotion never blocks the
    # digest (rejections are expected — they stay in 02-Draft with a
    # _failed/ marker).
    _promote_eligible_drafts(
        store, digest_domains if is_cross_domain_digest else [domain], caller="digest"
    )

    # --- Content-preference tier filtering (B-001) ---------------------------
    if content_preference != "both":
        filtered_entries = _filter_entries_by_content_preference(entries, content_preference)
        if len(filtered_entries) != len(entries):
            logger.info(
                "Excluded %d entries from digest for domain '%s' due to content_preference='%s'",
                len(entries) - len(filtered_entries),
                domain,
                content_preference,
            )
        entries = filtered_entries

    # --- Stale filtering (F51) -----------------------------------------------
    excluded_stale_count = 0
    if not include_stale:
        # Resolve domain-specific TTL and freshness threshold from the single
        # source of truth (issue #366).
        from autoinfo.config import resolve_domain_freshness  # noqa: PLC0415

        ttl_days, freshness_threshold = resolve_domain_freshness(domain)

        from autoinfo.kb import calculate_freshness_score  # noqa: PLC0415

        active_entries: list[dict[str, Any]] = []
        for entry in entries:
            entry_freshness = calculate_freshness_score(entry, ttl_days)
            entry["freshness_score"] = round(entry_freshness, 4)
            if entry_freshness < freshness_threshold:
                entry["is_stale"] = True
                excluded_stale_count += 1
            else:
                entry["is_stale"] = False
                active_entries.append(entry)

        if excluded_stale_count > 0:
            logger.info(
                "Excluded %d stale entries from digest for domain '%s'",
                excluded_stale_count,
                domain,
            )
        entries = active_entries

    # --- Stale-source guard (backup issue #52) --------------------------------
    if not include_stale and excluded_stale_count > 0 and not entries:
        stale_count = excluded_stale_count
        stale_msg = (
            f"All candidate entries for domain '{domain}' are stale "
            f"(excluded {stale_count} entr{'y' if stale_count == 1 else 'ies'} "
            f"older than the freshness threshold). "
            f"Refusing to generate an empty-shell product. "
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

    # --- LLM synthesis -------------------------------------------------------
    # Resolve the product template family up front (spec §2.4, todo 7) so the
    # synthesis prompt can request the product-specific fields; the render
    # site below reuses this resolution. Agent format is content-equivalent
    # to markdown, so its family resolves against the markdown template file
    # (todo 22) — otherwise premium-briefing/enterprise-briefing agent output
    # would never request the per-product synthesis fields.
    variant = FORMAT_TO_VARIANT.get(format, format)
    family_variant = "md" if variant == "agent" else variant
    digest_family = (
        _resolve_digest_product_type(product_template, family_variant)
        if product_template is not None
        else "digest"
    )
    llm_synthesis: dict[str, Any] = {}
    # Default the synthesis/context entry set to the full candidate list;
    # premium/enterprise families replace it with a differentiated subset
    # below (issue #145).  Initialised here so context_entries below never
    # hits an unbound local when *entries* is empty.
    synthesis_entries: list[dict[str, Any]] = entries
    if entries:
        # Issue #46: prune the LLM-synthesis candidate list the same way #42
        # prunes References — low-value promo/obituary/celebrity entries must
        # not reach the Executive Summary's leading enumeration.  Clean
        # entries always stay; flagged entries are dropped for non-language
        # domains with >= _REF_LOW_VALUE_MIN_REAL_ENTRIES clean candidates and
        # demoted to the tail otherwise (language-learning keeps them as
        # teaching material).  Deterministic, no LLM.  The full *entries* list
        # still flows to References unchanged below.
        synthesis_entries = _sorted_ref_entries(entries, domain=domain)
        # Issue #145: premium/enterprise briefings source a DIFFERENTIATED
        # entry subset (data layer) so their references diverge — a prompt
        # directive alone cannot change a fixed reference set.  The subset
        # feeds both the LLM synthesis and the reference derivation below.
        synthesis_entries = _select_family_entry_subset(synthesis_entries, digest_family)
        prompt = _build_digest_llm_prompt(synthesis_entries, product_family=digest_family)
        if custom_instructions:
            prompt += f"\n\nAdditional instructions: {custom_instructions}"
        audience = _normalize_report_audience(target_audience)
        audience_prompt = _REPORT_AUDIENCE_PROMPTS.get(audience, "")
        if audience_prompt:
            prompt += f"\n\n{audience_prompt}"
        llm_synthesis = _call_llm_for_digest(
            prompt,
            config=llm_config,
            max_synthesis_attempts=max_synthesis_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
        )
    else:
        llm_synthesis = {}

    # Issue #217: if the LLM synthesis is empty or missing the D1-required
    # sections (intermittent empty output on long prompts), fall back to a
    # deterministic synthesis derived from the real entries so the product
    # stays complete and D1 never blocks it for empty sections.
    if entries and not (
        (llm_synthesis.get("executive_summary") or "").strip()
        and llm_synthesis.get("key_findings")
        and llm_synthesis.get("recommendations")
    ):
        mark_kb_fallback("digest_synthesis_empty")
        llm_synthesis = _deterministic_synthesis_fallback(entries)

    # -- Body-citation URL whitelist sanitizer (issue #207) -----------------
    # Mirror of the report path: cross-check every body-citation URL in the
    # LLM-produced digest text fields (incl. the magazine-digest
    # feature_story / editorial_intro) against the real KB source_url
    # whitelist so a fabricated re-slugged URL never reaches any render.
    _digest_whitelist = {
        str(e.get("source_url") or "").strip()
        for e in entries
        if str(e.get("source_url") or "").strip()
    }
    if _digest_whitelist and isinstance(llm_synthesis, dict):
        for _key in ("executive_summary", "editorial_intro", "feature_story"):
            _val = llm_synthesis.get(_key)
            if isinstance(_val, str) and _val:
                llm_synthesis[_key] = _sanitize_report_urls(_val, _digest_whitelist)
        for _key in (
            "key_findings",
            "recommendations",
            "implications",
            "action_required",
            "trends",
        ):
            _vals = llm_synthesis.get(_key)
            if isinstance(_vals, list):
                for _i, _v in enumerate(_vals):
                    if isinstance(_v, str) and _v:
                        _vals[_i] = _sanitize_report_urls(_v, _digest_whitelist)
                    elif isinstance(_v, dict):
                        for _field in _v:
                            if isinstance(_v[_field], str) and _v[_field]:
                                _v[_field] = _sanitize_report_urls(_v[_field], _digest_whitelist)
        for _key in ("risks", "key_metrics"):
            _vals = llm_synthesis.get(_key)
            if isinstance(_vals, list):
                for _v in _vals:
                    if not isinstance(_v, dict):
                        continue
                    for _field in _v:
                        if isinstance(_v[_field], str) and _v[_field]:
                            _v[_field] = _sanitize_report_urls(_v[_field], _digest_whitelist)

    # --- Build template context ----------------------------------------------
    # Issue #138: day-granularity timestamp (no microseconds) — the full
    # ISO instant (…T08:56:52.820676+00:00) leaked an internal precision
    # marker into every product header/footer.
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Issue #318/#99: the H1 product word follows the resolved product family
    # (digest/report/tutorial/presentation/premium-briefing/column/
    # magazine-digest/enterprise-briefing) instead of being hardcoded to
    # "Digest"; the period label still drives the Daily/Weekly/Monthly prefix.
    # The default digest family keeps the historical
    # "{period_label} Digest — {domain}" title byte-identical.
    digest_h1_word = _product_h1_word(digest_family)
    # Issue #145: for premium/enterprise briefings the rendered product (and
    # its References) must draw from the DIFFERENTIATED entry subset selected
    # above — not the full candidate list — so the two paid products source
    # different entries.  Other families keep the full list.
    context_entries = (
        synthesis_entries
        if digest_family in ("premium-briefing", "enterprise-briefing")
        else entries
    )
    context = {
        "title": f"{period_label} {digest_h1_word} \u2014 {digest_title_domain_display}",
        "domain": digest_title_domain,
        "period": period,
        "period_label": period_label,
        "date_from": date_from,
        "date_to": date_to,
        "generated_at": generated_at,
        "entries": context_entries,
        "llm_synthesis": llm_synthesis,
        "target_audience": target_audience,
        "source_tier_badge": _source_tier_badge_enabled(),
    }
    # Issue #151: the digest path renders presentation.md.j2 via the generic
    # context, which previously carried no ``slides`` / ``topic`` keys — so
    # ``slides|length`` was 0 and every digest-path presentation was an empty
    # shell (Slides: 0).  Populate them for the presentation family: use the
    # LLM synthesis slides when present, else derive KB-backed slides from the
    # entries (same fallback the standalone generate_presentation uses).
    if digest_family == "presentation":
        synth_slides = llm_synthesis.get("slides") if isinstance(llm_synthesis, dict) else None
        if isinstance(synth_slides, list) and synth_slides:
            slides = synth_slides
        else:
            mark_kb_fallback("digest_presentation_slides_derived")
            slides = _fallback_slides_from_entries(context_entries, _PRESENTATION_SLIDE_COUNT)
        context["slides"] = slides
        context["topic"] = (
            str(llm_synthesis.get("topic") or period_label).strip()
            if isinstance(llm_synthesis, dict)
            else period_label
        )
        context["description"] = (
            str(llm_synthesis.get("description") or "").strip()
            if isinstance(llm_synthesis, dict)
            else ""
        )
        # Issue #182: keep the deck header Audience populated even when the
        # digest path did not receive an explicit target_audience.
        context["target_audience"] = (
            str(context.get("target_audience") or "").strip() or "executive"
        )

    # --- Render --------------------------------------------------------------
    if format == "agent":
        # Product templates only carry markdown variants, so agent format
        # always renders the JSON-LD payload — which surfaces the
        # per-product synthesis fields when present (todo 22).
        rendered = _render_agent_json(entries, context)
        # Persist the per-product analysis fields to the linked KB entries
        # (todo 24) — no-op when the synthesis carries no product fields.
        _persist_product_analysis_to_kb(store, entries, llm_synthesis)
    elif product_template is not None:
        product_type = digest_family
        pt_context = _normalize_digest_product_context(
            context,
            domain,
            product_family=digest_family,
            ref_limit=ref_limit,
        )
        rendered = product_template.render(product_type, variant, pt_context)
        rendered = _clean_skeleton_placeholders(rendered)
        rendered = _strip_entry_placeholders(rendered)
        rendered = _strip_fake_source_placeholders(rendered)
    elif format == "json":
        rendered = _render_json(context)
    elif format == "html":
        rendered = _render_digest_html(context)
    elif format == "audio":
        markdown_text = _render_markdown(context)
        mp3_bytes = _render_audio(markdown_text)
        rendered = base64.b64encode(mp3_bytes).decode("ascii")
    elif format in ("epub", "audiobook"):
        from autoinfo.output.ebook import render_audiobook, render_epub  # noqa: PLC0415

        ebook_chapters = _digest_chapters(context)
        if format == "epub":
            ebook_result = render_epub(
                title=str(context.get("title", "AutoInfo Digest")),
                author="AutoInfo",
                lang="en",
                chapters=ebook_chapters,
            )
        else:
            ebook_result = render_audiobook(ebook_chapters)
        rendered = ebook_result["data_b64"]
    else:
        rendered = _render_markdown(context)

    # --- Source attribution (F46) ------------------------------------------
    if is_cross_domain_digest:
        all_src_configs_d: list[Any] = []
        for d in digest_domains:
            all_src_configs_d.extend(_get_domain_source_configs(d))
        src_configs = all_src_configs_d
    else:
        src_configs = _get_domain_source_configs(domain)
    if src_configs and entries:
        entry_urls = {
            (e.get("source_url") or "").strip().rstrip("/") for e in entries if e.get("source_url")
        }
        used_sources = [s for s in src_configs if (s.url or "").strip().rstrip("/") in entry_urls]
        if used_sources:
            attribution = _build_attribution_footer(used_sources, format)
            if attribution:
                if format in ("json", "agent"):
                    try:
                        data = json.loads(rendered)
                        data["sources"] = json.loads(
                            _build_attribution_footer(used_sources, "json")
                        )
                        rendered = json.dumps(data, indent=2, ensure_ascii=False, default=str)
                    except (json.JSONDecodeError, TypeError):
                        pass
                else:
                    # Text formats get a plain attribution footer. Binary
                    # formats (audio/epub/audiobook) carry base64 payloads —
                    # appending text would corrupt the base64 and make
                    # b64decode fail with "string argument should contain
                    # only ASCII characters" (F46 regression, 2026-08-11).
                    if format not in ("audio", "epub", "audiobook"):
                        rendered = rendered.rstrip() + "\n\n" + attribution

    # --- Record consumption event (CD-018) -----------------------------------
    if user_id:
        try:
            from autoinfo.consumption import ConsumptionStore  # noqa: PLC0415

            ConsumptionStore().record_event(
                user_id=user_id,
                product_type="digest",
                product_id=f"{digest_title_domain}-{period}",
                event_type="delivered",
                metadata={
                    "domain": digest_title_domain,
                    "period": period,
                    "format": format,
                    "entries_count": len(entries),
                    "stale_excluded": excluded_stale_count if not include_stale else 0,
                },
            )
        except Exception:
            logger.warning(
                "Failed to record consumption event for user '%s'",
                user_id,
                exc_info=True,
            )

    # --- CJK leak hard-check (issue #181) -----------------------------------
    if format not in ("audio", "epub", "audiobook"):
        _warn_cjk_leak(digest_title_domain, "digest", rendered)

    # --- Delivery gates (D1-D3) ---------------------------------------------
    if delivery_gate_configs is not None:
        result = _apply_delivery_gates(
            rendered_output=rendered,
            output_format=format,
            entries=entries,
            context=context,
            product_type=product_type,
            delivery_gate_configs=delivery_gate_configs,
            fallback_render_fn=lambda: _render_markdown(context),
            llm_config=llm_config,
        )
        result = _apply_min_content_guard(result, entries, product_type)
        if user_id:
            _try_notify_content_ready(
                user_id=user_id,
                product_type="digest",
                title=f"{period_label} {digest_h1_word} \u2014 {digest_title_domain_display}",
            )
        _fire_agent_notification(
            "new_digest",
            result.output if isinstance(result, DeliveryOutput) else rendered,
            product_id=f"{digest_title_domain}-{period}",
        )
        return result

    if user_id:
        _try_notify_content_ready(
            user_id=user_id,
            product_type="digest",
            title=f"{period_label} {digest_h1_word} — {domain}",
        )
    _fire_agent_notification("new_digest", rendered, product_id=f"{digest_title_domain}-{period}")
    return rendered


# ---------------------------------------------------------------------------
# Report generation — structured Jinja2 + LLM reports from KB entries
# ---------------------------------------------------------------------------


def generate_report(
    domain: str,
    collection_id: str | None = None,
    format: str = "markdown",
    period: str = "weekly",
    custom_instructions: str = "",
    target_audience: str = "",
    product_template: ProductTemplate | None = None,
    product_type: str = "PROCESSED",
    delivery_gate_configs: dict[str, dict[str, Any]] | _DeliveryGatesBypass | None = None,
    user_id: str = "",
    report_type: str = "standard",
    domains: list[str] | None = None,
    llm_config: Config | None = None,
    language: str = "",
    ref_limit: int | None = None,
    *,
    max_synthesis_attempts: int = _RETRY_MAX_ATTEMPTS,
    retry_backoff_seconds: float = _RETRY_BACKOFF_SECONDS,
) -> str | DeliveryOutput:
    """Generate a structured report for the given *domain* (or *domains*).

    Groups KB entries by theme using an LLM, produces an executive
    summary, and renders the result through the Jinja2 report template.

    Parameters
    ----------
    domain : str
        Domain to generate the report for (e.g. ``"medical-research"``).
        When *domains* is provided with 2+ entries, *domain* is still used
        for backward-compatible metadata but entries are aggregated from
        all listed domains.
    collection_id : str, optional
        Optional collection ID to scope the report to a specific
        collection run.  When omitted, all KB entries for the domain(s)
        are included.
    format : str, optional
        Output format (default ``"markdown"``).  Supports ``"markdown"``,
        ``"json"``, ``"html"``, ``"audio"``, ``"agent"``, ``"epub"``,
        ``"audiobook"``.  The ``"agent"`` format returns JSON-LD
        (``@type: KnowledgeDigest``) optimized for LLM re-consumption.
    period : str, optional
        Report period label (default ``"weekly"``).  One of ``"daily"``,
        ``"weekly"``, ``"monthly"``.  Used for metadata in JSON output.
        Unknown values raise :class:`ValueError`.
    custom_instructions : str, optional
        Optional string of additional instructions to append to the LLM
        generation prompt.  Ignored when empty/absent.
    report_type : str, optional
        Report type that controls section structure and content focus
        (default ``"standard"``).  Supported values: ``"standard"``
        (unchanged existing behavior), ``"industry"`` (domain-specific
        trends), ``"competitive"`` (entity comparison), ``"trend"``
        (time-series analysis), ``"daily-briefing"`` (curated top-N).
        Unknown values raise :class:`ValueError`.
    target_audience : str, optional
        Target audience for tone and depth adaptation (e.g. ``"researcher"``,
        ``"executive"``, ``"investor"``, ``"clinician"``, ``"student"``,
        ``"general"``).  Ignored when empty/absent.
    product_template:
        Optional :class:`ProductTemplate` instance for template rendering.
        When provided, the report is rendered through the product template
        system (with domain-specific overrides).  When ``None`` (default),
        the existing direct Jinja2 rendering is used (backward compatible).
        The product's ``access_level`` controls freemium gating (G15).
    product_type:
        Product type for delivery gate checking.  ``"PROCESSED"`` (default)
        enables D1-D3 checks when *delivery_gate_configs* is provided.
        ``"RAW"`` skips all delivery gates.
    delivery_gate_configs:
        Optional dict of ``{gate_name: config_dict}`` for D1-D3 delivery
        gates.  When provided, D1-D3 are run after rendering and the return
        type changes to :class:`DeliveryOutput`.  When ``None`` (default),
        no gates are run and a plain ``str`` is returned (backward
        compatible).
    domains : list[str], optional
        Optional list of domain names for cross-domain report generation.
        When provided with 2+ domains, entries are aggregated from all
        listed domains.  Each entry is labeled with its source domain.
        A special cross-domain LLM prompt encourages synthesis across
        domains.  When ``None`` or has fewer than 2 entries, the existing
        single-domain behavior is used (backward compatible).
    ref_limit:
        Optional maximum number of KB references to include in the rendered
        product.  Defaults to ``output.ref_limit`` from the project config
        (60).  References are sorted by (has non-empty summary desc,
        ``relevance_score`` desc) and capped at *ref_limit* at the
        context-build site, so title-only entries (empty summary, e.g.
        ProductHunt) de-prioritize.  All render formats (markdown/html/json/
        agent/audio/epub/video) are capped uniformly (issue #11).

    Returns
    -------
    str or DeliveryOutput
        Plain ``str`` when *delivery_gate_configs* is ``None`` (default).
        :class:`DeliveryOutput` with gate results when *delivery_gate_configs*
        is provided.

    Raises
    ------
    ValueError
        If *format* is unsupported, if *period* is not one of ``"daily"``,
        ``"weekly"``, ``"monthly"``, or if *report_type* is unknown.
    FileNotFoundError
        If the Jinja2 template file is not found.
    """
    if format not in ("markdown", "json", "html", "audio", "agent", "video", "epub", "audiobook"):
        raise ValueError(
            f"Unsupported output format: {format!r}. "
            f"Supported: markdown, json, html, audio, agent, video, epub, audiobook"
        )

    if report_type not in _VALID_REPORT_TYPES:
        raise ValueError(
            f"Unknown report type: {report_type!r}. Supported: {', '.join(_VALID_REPORT_TYPES)}"
        )

    if period not in PERIOD_DAYS:
        raise ValueError(
            f"Invalid period '{period}'. Must be one of: {', '.join(sorted(PERIOD_DAYS))}"
        )

    # --- Resolve delivery-gate config (issue #298: default-on in production) --
    delivery_gate_configs = _resolve_delivery_gate_configs(domain, delivery_gate_configs)

    # --- Free-tier quota gate (todo 12) — named users only; user_id="" (batch) skips

    check_free_tier_generation(
        user_id=user_id, domain=domain, product_type="report", raise_on_block=True
    )

    # --- Determine cross-domain mode -----------------------------------------
    is_cross_domain: bool = domains is not None and len(domains) >= 2
    if is_cross_domain:
        report_domains: list[str] = domains  # type: ignore[assignment]
        report_title_domain: str = "Cross-Domain"
    else:
        report_domains = [domain]
        report_title_domain = domain
    # Issue #144: H1 title uses the user-facing domain name; the slug stays
    # for internal product_id / domain keys.
    report_title_domain_display: str = _domain_display_name(report_title_domain)

    # --- Auto-load content_preference from user profile (B-001) --------------
    content_preference: str = _resolve_content_preference(user_id)
    source_tier_badge: bool = _source_tier_badge_enabled()

    # --- Freemium access gating (G15) ----------------------------------------
    if user_id and product_template is not None:
        product_access = getattr(product_template, "access_level", "free")
        if product_access != "free":
            from autoinfo.billing import check_access  # noqa: PLC0415

            access_result = check_access(user_id, product_access)
            if not access_result["allowed"]:
                blocked_message = (
                    f"# {report_title_domain_display} \u2014 Report\n\n"
                    f"**{access_result['upgrade_prompt'] or 'Access denied.'}**\n\n"
                    f"_Reason_: {access_result['reason']}\n\n"
                    f"_Access level required_: `{product_access}`\n"
                    f"_Your status_: {access_result['profile_status']} "
                    f"(plan: {access_result['plan']})\n"
                )
                if delivery_gate_configs is not None:
                    return DeliveryOutput(
                        output=blocked_message,
                        gate_results={},
                        delivery_blocked=True,
                        delivery_format=format,
                        warnings=[f"G15 blocked: {access_result['reason']}"],
                    )
                return blocked_message

    # -- Load KB entries --------------------------------------------------
    from autoinfo.llm import LLMExtractor  # noqa: PLC0415

    reset_llm_provenance()
    kb_store = KBStore()
    _select_story_was_empty = False
    if is_cross_domain:
        entries: list[dict[str, Any]] = []
        for d in report_domains:
            domain_entries = kb_store.list_entries(d, limit=5000)
            for e in domain_entries:
                if "domain" not in e:
                    e["domain"] = d
            entries.extend(domain_entries)
    else:
        # Single-domain story set — shared with digest/presentation (#119).
        # The report's downstream filters (product/empty/lang/stale) still
        # run on the shared set; content MAY change vs the old all-time load.
        entries, _date_range, _select_story_was_empty = _select_story_set(
            kb_store,
            domain,
            period=period,
            product="report",
            query_limit=5000,
        )

    # --- Promotion trigger (T6): promote eligible 02-Draft entries ------------
    # Best-effort per entry — a rejected/failed promotion never blocks the
    # report (rejections stay in 02-Draft with a _failed/ marker).
    _promote_eligible_drafts(
        kb_store, report_domains if is_cross_domain else [domain], caller="report"
    )

    # --- Content-preference tier filtering (B-001) ---------------------------
    if content_preference != "both":
        filtered_entries = _filter_entries_by_content_preference(entries, content_preference)
        if len(filtered_entries) != len(entries):
            logger.info(
                "Excluded %d entries from report for domain '%s' due to content_preference='%s'",
                len(entries) - len(filtered_entries),
                domain,
                content_preference,
            )
        entries = filtered_entries

    # --- Test/empty entry filtering (issue #298 — layer 1) -------------------
    # Drop empty/test/placeholder entries BEFORE synthesis and BEFORE render.
    # Real Draft/Wiki entries with an empty DB summary but file content are
    # first enriched (issue #326) so the report Sections are never an empty
    # shell from real KB data.
    entries = _filter_product_entries(_enrich_product_entries(entries))
    # Near-duplicate convergence (issue #69) — see generate_digest.
    entries = _converge_near_duplicates(entries)

    # Issue #185: the window query returned rows but they were ALL dropped by
    # the product/empty/synthesized filter (e.g. a window that holds only a
    # synthesized digest placeholder draft) — the report would be an empty
    # shell even though valid out-of-window content exists.  Recover the
    # full-domain set (same relaxation as the digest's #83 fallback) and
    # re-run the identical filter chain.  Single-domain only — the
    # cross-domain path has no window fallback.
    if not entries and not _select_story_was_empty and not is_cross_domain:
        logger.info(
            "In-window entries for domain '%s' all dropped by product/empty/"
            "synthesized filters — falling back to full domain set",
            domain,
        )
        entries = _filter_product_entries(
            _enrich_product_entries(kb_store.list_entries(domain=domain, limit=5000))
        )
        entries = _converge_near_duplicates(entries)

    # --- Language filter (issue #309 / #317) --------------------------------
    # An explicit param wins; otherwise the domain default fills in;
    # cross-domain never auto-picks one domain's default — EXCEPT when every
    # contributing domain shares the same non-bilingual default_language
    # (issue #186): a cross ai+fin English report must drop Chinese 36kr raw
    # entries so the product stays language-coherent.
    effective_language = _resolve_effective_language(language, domain, cross_domain=is_cross_domain)
    if not effective_language and is_cross_domain:
        effective_language = _cross_domain_shared_language(report_domains)
    if effective_language:
        entries, _ = _filter_entries_by_language_product_safe(entries, effective_language)

    # --- Per-domain exclude_keywords filter (issue #319) ---------------------
    # Cross-domain noise guard: drop entries matching their own domain's
    # exclude_keywords blacklist BEFORE thematic grouping / LLM synthesis.
    entries = _filter_entries_by_domain_exclusions(entries, domain)

    # --- Entry cap (issue #106) ----------------------------------------------
    # Uncapped entries flowing into _group_by_theme blow past the CLI timeout on
    # heavy reasoning LLMs (470 entries × 8/batch ÷ 4 workers × ~30s+ each).
    # Align with generate_digest's query_limit default (200) so report generates
    # reliably on the same LLM as the other products. The grouping chaos-guard is
    # kept independently and complements this cap.
    entries = entries[:200]

    # --- Source-label enrichment (issue #325) --------------------------------
    # Mirror the digest path: stamp the derived specific source name on every
    # entry so ALL report-path surfaces (markdown references, section entry
    # tables, JSON entries, product-template variants column / premium-briefing
    # / enterprise-briefing / magazine-digest) render the specific source
    # instead of the generic "(RSS)" for stale pre-#323 entries.  In-place
    # mutation flows into section items because _group_by_theme reuses the same
    # entry dict objects.
    entries = _label_entries(entries, domain)

    if not entries:
        rendered: str
        if format in ("json", "agent"):
            empty_data: dict[str, Any] = {
                "title": f"{report_title_domain_display} \u2014 Report",
                "summary": "",
                "entries": [],
                "metadata": {
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "domain": report_title_domain,
                    "period": period,
                    "format": format,
                    "entry_count": 0,
                },
            }
            if format == "agent":
                empty_data["@context"] = _JSONLD_DIGEST["@context"]
                empty_data["@type"] = _JSONLD_DIGEST["@type"]
                empty_data["uuid"] = str(uuid.uuid4())
                empty_data["trends"] = []
            rendered = json.dumps(empty_data, indent=2, ensure_ascii=False, default=str)
        elif format == "html":
            rendered = _render_empty_report_html(report_title_domain)
        elif format == "audio":
            empty_md = _render_empty_report(report_title_domain)
            mp3_bytes = _render_audio(empty_md)
            rendered = base64.b64encode(mp3_bytes).decode("ascii")
        elif format in ("epub", "audiobook"):
            from autoinfo.output.ebook import render_audiobook, render_epub  # noqa: PLC0415

            empty_chapters = [
                (
                    f"{report_title_domain_display} \u2014 Report",
                    _render_empty_report(report_title_domain),
                )
            ]
            if format == "epub":
                ebook_result = render_epub(
                    title=f"{report_title_domain_display} \u2014 Report",
                    author="AutoInfo",
                    lang="en",
                    chapters=empty_chapters,
                )
            else:
                ebook_result = render_audiobook(empty_chapters)
            rendered = ebook_result["data_b64"]
        elif format == "video":
            rendered = _render_video_scaffold({}, report_title_domain, sections=None)
        else:
            rendered = _render_empty_report(report_title_domain)

        if delivery_gate_configs is not None:
            result = _apply_delivery_gates(
                rendered_output=rendered,
                output_format=format,
                entries=[],
                context={},
                product_type=product_type,
                delivery_gate_configs=delivery_gate_configs,
            )
            return _apply_min_content_guard(result, [], product_type)
        return rendered

    # -- Build reference list from entries --------------------------------
    # #325: derive the specific source label for entries whose stored
    # source_platform is a generic placeholder (pre-#323 'rss' etc.).
    # #11: cap the references at ref_limit (default output.ref_limit = 60).
    # The sort MUST run on the FULL entries list BEFORE the ref dicts are
    # built — the ref dicts drop relevance_score/summary, so capping on the
    # ref dicts would silently lose the (has summary, relevance) ordering.
    _ref_limit = ref_limit if ref_limit is not None else _output_config_ref_limit()
    _src_configs = _get_domain_source_configs(domain)
    references = []
    for e in _sorted_ref_entries(entries, domain=domain)[:_ref_limit]:
        _label = _derive_source_label(
            e,
            e.get("domain", domain),
            source_configs=_src_configs,
        )
        references.append(
            {
                "title": e.get("title", ""),
                "source_url": e.get("source_url", ""),
                "source_type": e.get("source_type", ""),
                # Raw internal platform id + derived user-facing label (#325):
                # user_source_label shows the label only when it differs.
                "source_platform": e.get("source_platform", ""),
                "source_label": _label,
                "domain": e.get("domain", domain),
                "description": (
                    str(e.get("summary") or "").strip()
                    or str(e.get("content") or "")[:120].strip()
                    or f"{_label} item"
                ),
            }
        )

    # -- Thematic grouping via LLM ----------------------------------------
    _reset_grouping_degraded()
    extractor = LLMExtractor()
    groupings = _group_by_theme(
        extractor,
        entries,
        domain=domain,
        domains=report_domains if is_cross_domain else None,
    )

    # -- Inject report-type prompt into custom instructions ------------------
    effective_instructions = custom_instructions
    if report_type != "standard":
        type_prompt = _REPORT_TYPE_PROMPTS.get(report_type, "")
        if type_prompt:
            effective_instructions = (
                f"{custom_instructions}\n\n{type_prompt}" if custom_instructions else type_prompt
            )

    # -- Generate executive summary via LLM --------------------------------
    # Resolve the product template family up front (spec §2.4, todo 7) so
    # the synthesis can request the product-specific fields; the render
    # site below reuses this resolution. Agent format is content-equivalent
    # to markdown, so its family resolves against the markdown template file
    # (todo 22) — otherwise premium-briefing/enterprise-briefing agent output
    # would never request the per-product synthesis fields.
    variant = FORMAT_TO_VARIANT.get(format, format)
    family_variant = "md" if variant == "agent" else variant
    report_family = (
        _resolve_report_product_type(product_template, family_variant, report_type)
        if product_template is not None
        else ("column" if report_type == "column" else "report")
    )
    summary_result = _generate_executive_summary(
        extractor,
        entries,
        groupings,
        effective_instructions,
        target_audience=target_audience,
        domains=report_domains if is_cross_domain else None,
        product_family=report_family,
        max_synthesis_attempts=max_synthesis_attempts,
        retry_backoff_seconds=retry_backoff_seconds,
    )
    # The synthesis returns a dict of ``{executive_summary, key_findings,
    # recommendations}`` (plus the §2.4 product fields for product template
    # families).  Accept a bare string for backward compatibility (legacy
    # callers / direct mocks) — treated as summary only.
    if isinstance(summary_result, dict):
        executive_summary = summary_result.get("executive_summary", "") or ""
        # Issue #279: normalize findings to {text, source_url} objects.
        key_findings = [
            f if isinstance(f, dict) else {"text": str(f)}
            for f in (summary_result.get("key_findings") or [])
        ]
        recommendations = [str(r) for r in (summary_result.get("recommendations") or [])]
        implications = [str(i) for i in (summary_result.get("implications") or [])]
        action_required = [str(a) for a in (summary_result.get("action_required") or [])]
        risks = [
            {
                k: str(v)
                for k, v in r.items()
                if k in ("title", "likelihood", "impact", "mitigation")
            }
            for r in (summary_result.get("risks") or [])
            if isinstance(r, dict)
        ]
        key_metrics = [
            {k: str(v) for k, v in m.items() if k in ("metric", "value", "source")}
            for m in (summary_result.get("key_metrics") or [])
            if isinstance(m, dict)
        ]
        # Issue #131 + #148: the LLM echoes the synthesis prompt's "Entry N"
        # internal numbering into free-text product fields (key_metrics[].source
        # #131; recommendations / implications / action_required / key_findings
        # #148).  Internal KB row references must never leak to end users —
        # strip "(Entry N)" / "Entry N" markers from EVERY LLM-produced text
        # field before it reaches a template.
        for _m in key_metrics:
            _src = _m.get("source", "")
            _m["source"] = _strip_entry_refs(_src)
        recommendations = [_strip_entry_refs(r) for r in recommendations]
        implications = [_strip_entry_refs(i) for i in implications]
        action_required = [_strip_entry_refs(a) for a in action_required]
        for _f in key_findings:
            if isinstance(_f, dict) and _f.get("text"):
                _f["text"] = _strip_entry_refs(str(_f["text"]))
    else:
        executive_summary = str(summary_result or "")
        key_findings = []
        recommendations = []
        implications = []
        risks = []
        action_required = []
        key_metrics = []

    # -- Issue #217 follow-up: empty LLM synthesis → KB-derived fallback ----
    # DeepSeek empty/truncated synthesis (issue #178) must not ship a
    # section-less report: D1 rejects key_findings/summary/recommendations.
    # Derive those sections deterministically from the KB entries actually
    # used in the report — real domain content, never fabricated.
    if not executive_summary or not key_findings or not recommendations:
        mark_kb_fallback("report_synthesis_empty")
        logger.info(
            "LLM synthesis empty/partial for report (domain=%s, "
            "exec_summary=%d chars, key_findings=%d, recommendations=%d) — "
            "KB-derived fallback",
            domain,
            len(executive_summary or ""),
            len(key_findings),
            len(recommendations),
        )
        ranked = sorted(
            (e for e in entries),
            key=lambda e: float(e.get("relevance_score") or 0.0),
            reverse=True,
        )
        if not executive_summary:
            executive_summary = (
                f"{domain} intelligence briefing — {len(entries)} KB entries "
                f"across {len(groupings)} themes, distilled from the tracked "
                f"source set."
            )
        if not key_findings:
            key_findings = [
                {
                    "text": (
                        f"{e.get('title', 'Untitled entry')} \u2014 "
                        f"{str(e.get('summary') or '(no summary)')[:160]}"
                    ),
                    **(
                        {"source_url": str(e.get("source_url") or "").strip()}
                        if (e.get("source_url") or "").strip()
                        else {}
                    ),
                }
                for e in ranked[:5]
                if e.get("title")
            ]
        if not recommendations:
            recommendations = [
                f"Monitor {e.get('title', 'this topic')} for follow-up "
                "developments and validation from additional sources."
                for e in ranked[:3]
                if e.get("title")
            ]

    # -- Deterministic per-takeaway fields (issue #329) ----------------------
    # premium-briefing's takeaway layer renders per-takeaway implication /
    # risk / action by index-aligning with key_findings.  When the LLM
    # synthesis carries none (line 5053-5056 initializes them to []) or slot
    # values that are empty / `_No ..._` placeholder-shaped, the template's
    # `{% else %}` empty-state renders `_No ..._` placeholders.  Backfill each
    # slot per-index with the deterministic fallback derived from the ranked
    # entries (same pattern as #316/#326 column sections and the KB fallback
    # above), only for premium; placeholder-element case #357.
    if report_family == "premium-briefing":
        implications, risks, action_required = _fill_premium_takeaway_fields(
            implications,
            risks,
            action_required,
            entries,
            domain,
        )

    # -- Enterprise/premium key_findings cap (issue #11, decision a) --------
    # The enterprise-briefing template renders the selection-scope label
    # ``selected {{ key_findings|length }} of {{ references|length }}``.  The
    # PRIMARY synthesis key_findings is LLM-unbounded (only the §2.4 re-prompt
    # is bounded by _DEDICATED_PRODUCT_PROMPT_MAX_FINDINGS), so a ref_limit
    # below the findings count would invert the label.  Cap the findings in
    # the report data to min(12, len(references)) for the families that
    # render the label (premium/enterprise), leaving the summary + findings
    # count consistent.
    if report_family in ("premium-briefing", "enterprise-briefing"):
        key_findings = _cap_product_key_findings(key_findings, references)

    # -- Build report data -------------------------------------------------
    # #325: every section item carries the derived source label.  When the
    # entry was already stamped by _label_entries (the real generate_report
    # path), reuse it; when the grouping path returns unlabeled entries (e.g.
    # tests patching _group_by_theme, or a grouping that rebuilds entry
    # dicts), derive the label here so no section surface shows "(RSS)".
    sections = [
        ReportSection(
            title=g["theme"],
            content=g.get("description", ""),
            items=[
                {
                    "title": e.get("title", ""),
                    "summary": e.get("summary", ""),
                    "source_url": e.get("source_url", ""),
                    "source_type": e.get("source_type", ""),
                    "source_platform": (
                        e.get("source_label", "")
                        or _derive_source_label(e, str(e.get("domain") or domain))
                        or e.get("source_platform", "")
                    ),
                    "source_label": (
                        e.get("source_label", "")
                        or _derive_source_label(e, str(e.get("domain") or domain))
                        or e.get("source_platform", "")
                    ),
                    "relevance_score": e.get("relevance_score", 0),
                    "source_tier": e.get("source_tier"),
                    "domain": e.get("domain", domain),
                }
                for e in g["entries"]
            ],
        )
        for g in groupings
    ]

    # Issue #318/#99: the report H1 product word follows the resolved product
    # family when a product template is used (tutorial/presentation/
    # premium-briefing/column/enterprise-briefing); the default report path
    # (no product_template, incl. report_type="column" T40) keeps the
    # historical "{domain} — Report" title byte-identical.
    report_h1_word = (
        _product_h1_word(report_family, default="Report")
        if product_template is not None
        else "Report"
    )

    # -- Honest-degradation annotation (issue #120, C4) ---------------------
    # The rendered report must say "This edition groups developments by
    # source" when the grouping degraded (LLM fail / chaos / no groups)
    # instead of silently presenting source-type/keyword headings as
    # semantic themes.  Rephrased from "Grouped by source — not semantic
    # topics" (issue #134): the old wording was internal pipeline jargon
    # (R2 leak to end users); the new copy is user-meaningful while still
    # honest about the grouping method.
    # The digest/column paths annotate at their own seams; the report path
    # consumes the module-level flag the degradation seams set.
    report_degraded_reason = (
        ("no_groups" if _single_general_group(groupings) else "llm_failure")
        if _grouping_degraded
        else ""
    )
    grouping_degradation_marker = (
        _grouping_degradation_marker(report_degraded_reason) if report_degraded_reason else ""
    )

    # -- Body-citation URL whitelist sanitizer (issue #207) -----------------
    # The report synthesis may cite a fabricated re-slugged URL (e.g. a
    # "…/a16z-brings-growth-fund-to-8-5b-days-after-launching-a-new-1-1b-fund/"
    # 404 that quality_gate C5 only caught post-hoc).  Cross-check every
    # body-citation URL in the LLM-produced text fields against the real KB
    # source_url whitelist so a fabricated slug never reaches any render
    # format (markdown/html/json/agent flow through report_data.references is
    # untouched — its URLs are the real KB source_urls).
    _report_whitelist = {
        str(e.get("source_url") or "").strip()
        for e in entries
        if str(e.get("source_url") or "").strip()
    }
    if _report_whitelist:
        executive_summary = _sanitize_report_urls(executive_summary, _report_whitelist)
        for _f in key_findings:
            if isinstance(_f, dict) and _f.get("text"):
                _f["text"] = _sanitize_report_urls(str(_f["text"]), _report_whitelist)
        recommendations = [_sanitize_report_urls(r, _report_whitelist) for r in recommendations]
        implications = [_sanitize_report_urls(i, _report_whitelist) for i in implications]
        action_required = [_sanitize_report_urls(a, _report_whitelist) for a in action_required]
        for _r in risks:
            for _k in ("title", "likelihood", "impact", "mitigation"):
                if _r.get(_k):
                    _r[_k] = _sanitize_report_urls(str(_r[_k]), _report_whitelist)
        for _m in key_metrics:
            for _k in ("metric", "value", "source"):
                if _m.get(_k):
                    _m[_k] = _sanitize_report_urls(str(_m[_k]), _report_whitelist)
        for _s in sections:
            if _s.content:
                _s.content = _sanitize_report_urls(_s.content, _report_whitelist)

    report_data = ReportData(
        title=f"{report_title_domain_display} \u2014 {report_h1_word}",
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        domain=report_title_domain,
        collection_id=collection_id or "",
        executive_summary=executive_summary,
        key_findings=key_findings,
        recommendations=recommendations,
        implications=implications,
        risks=risks,
        action_required=action_required,
        key_metrics=key_metrics,
        sections=sections,
        references=references,
        grouping_degradation_marker=grouping_degradation_marker,
    )

    # -- Build context for delivery gates ----------------------------------
    report_context: dict[str, Any] = {
        "llm_synthesis": {
            "executive_summary": report_data.executive_summary,
            "key_findings": report_data.key_findings,
            "recommendations": report_data.recommendations,
        },
    }

    # -- Render -------------------------------------------------------------
    if format == "agent":
        # Build entry-like dicts from report items for JSON-LD rendering
        agent_entries: list[dict[str, Any]] = []
        for section in report_data.sections:
            for item in section.items:
                agent_entries.append(
                    {
                        "entry_id": item.get("entry_id", ""),
                        "title": item.get("title", ""),
                        "summary": item.get("summary", ""),
                        "source_url": item.get("source_url", ""),
                        # #325: derive the specific source label for stale
                        # pre-#323 entries (source_platform='rss') so the agent
                        # payload never carries the generic "rss" label.
                        "source_platform": _derive_source_label(item, item.get("domain", domain)),
                        "collected_at": item.get("date", ""),
                        "relevance_score": item.get("relevance_score", 0),
                        "tags": [],
                    }
                )
        # The llm_synthesis carries the per-product analysis fields from
        # ReportData (todo 7); _render_agent_json surfaces them (todo 22).
        agent_context: dict[str, Any] = {
            "domain": report_title_domain,
            "period": period,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "llm_synthesis": {
                "executive_summary": report_data.executive_summary,
                "key_findings": report_data.key_findings,
                "trends": [],
                "recommendations": report_data.recommendations,
                "implications": report_data.implications,
                "risks": report_data.risks,
                "action_required": report_data.action_required,
                "key_metrics": report_data.key_metrics,
            },
            "target_audience": target_audience,
        }
        rendered = _render_agent_json(agent_entries, agent_context)
        # Persist the per-product analysis fields to the linked KB entries
        # (todo 24). Report-path agent entries hardcode entry_id "" — the
        # helper falls back to source_url matching.
        _persist_product_analysis_to_kb(
            kb_store,
            agent_entries,
            {
                "implications": report_data.implications,
                "risks": report_data.risks,
                "action_required": report_data.action_required,
                "key_metrics": report_data.key_metrics,
            },
        )
    elif product_template is not None:
        pt_context = _report_data_to_dict(report_data, source_tier_badge=source_tier_badge)
        # The report product resolves to its own template family when the
        # registry row has an on-disk template (premium-briefing,
        # enterprise-briefing, column); everything else keeps the report
        # family ("column" stays column for T40 backward compatibility).
        product_type = report_family
        rendered = product_template.render(product_type, variant, pt_context)
        rendered = _clean_skeleton_placeholders(rendered)
        rendered = _strip_entry_placeholders(rendered)
        rendered = _strip_fake_source_placeholders(rendered)
    elif format == "json":
        rendered = _render_report_json(report_data, period=period)
    elif format == "html":
        rendered = _render_report_html(report_data, period=period)
    elif format == "audio":
        markdown_text = _render_report_template(report_data, source_tier_badge=source_tier_badge)
        mp3_bytes = _render_audio(markdown_text)
        rendered = base64.b64encode(mp3_bytes).decode("ascii")
    elif format in ("epub", "audiobook"):
        from autoinfo.output.ebook import render_audiobook, render_epub  # noqa: PLC0415

        report_chapters = _report_chapters(report_data)
        if not report_chapters:
            # Degenerate report (no summary/sections/references): render the
            # full template as a single chapter so the book is still valid.
            report_chapters = [
                (
                    report_data.title,
                    _render_report_template(report_data, source_tier_badge=source_tier_badge),
                )
            ]
        if format == "epub":
            ebook_result = render_epub(
                title=report_data.title,
                author="AutoInfo",
                lang="en",
                chapters=report_chapters,
                summary=report_data.executive_summary,
            )
        else:
            ebook_result = render_audiobook(report_chapters)
        rendered = ebook_result["data_b64"]
    elif format == "video":
        report_sections: list[dict[str, str]] = []
        for section in report_data.sections:
            for item in section.items:
                report_sections.append(
                    {
                        "heading": item.get("title", ""),
                        "body": item.get("summary", ""),
                    }
                )
        rendered = _render_video_scaffold(
            {},
            report_data.title if hasattr(report_data, "title") else report_title_domain,
            sections=report_sections,
        )
    else:
        rendered = _render_report_template(report_data, source_tier_badge=source_tier_badge)

    # -- Source attribution (F46) --------------------------------------------
    if is_cross_domain:
        all_src_configs: list[Any] = []
        for d in report_domains:
            all_src_configs.extend(_get_domain_source_configs(d))
        src_configs = all_src_configs
    else:
        src_configs = _get_domain_source_configs(domain)
    if src_configs and entries:
        entry_urls = {
            (e.get("source_url") or "").strip().rstrip("/") for e in entries if e.get("source_url")
        }
        used_sources = [s for s in src_configs if (s.url or "").strip().rstrip("/") in entry_urls]
        if used_sources:
            attribution = _build_attribution_footer(used_sources, format)
            if attribution:
                if format in ("json", "agent"):
                    try:
                        data = json.loads(rendered)
                        data["sources"] = json.loads(
                            _build_attribution_footer(used_sources, "json")
                        )
                        rendered = json.dumps(data, indent=2, ensure_ascii=False, default=str)
                    except (json.JSONDecodeError, TypeError):
                        pass
                else:
                    # Text formats get a plain attribution footer. Binary
                    # formats (audio/epub/audiobook) carry base64 payloads —
                    # appending text would corrupt the base64 and make
                    # b64decode fail with "string argument should contain
                    # only ASCII characters" (F46 regression, 2026-08-11).
                    if format not in ("audio", "epub", "audiobook"):
                        rendered = rendered.rstrip() + "\n\n" + attribution

    # --- Record consumption event (CD-018) -----------------------------------
    if user_id:
        try:
            from autoinfo.consumption import ConsumptionStore  # noqa: PLC0415

            ConsumptionStore().record_event(
                user_id=user_id,
                product_type="report",
                product_id=f"{report_title_domain}-{period}",
                event_type="delivered",
                metadata={
                    "domain": report_title_domain,
                    "format": format,
                    "entries_count": len(entries),
                    "collection_id": collection_id or "",
                },
            )
        except Exception:
            logger.warning(
                "Failed to record consumption event for user '%s'",
                user_id,
                exc_info=True,
            )

    # --- CJK leak hard-check (issue #181) -----------------------------------
    if format not in ("audio", "epub", "audiobook"):
        _warn_cjk_leak(report_title_domain, "report", rendered)

    # -- Delivery gates (D1-D3) ---------------------------------------------
    if delivery_gate_configs is not None:
        result = _apply_delivery_gates(
            rendered_output=rendered,
            output_format=format,
            entries=entries,
            context=report_context,
            product_type=product_type,
            delivery_gate_configs=delivery_gate_configs,
            fallback_render_fn=lambda: _render_report_template(
                report_data, source_tier_badge=source_tier_badge
            ),
            llm_config=llm_config,
        )
        result = _apply_min_content_guard(result, entries, product_type)
        if user_id:
            _try_notify_content_ready(
                user_id=user_id,
                product_type="report",
                title=f"{report_title_domain_display} \u2014 {report_h1_word}",
            )
        _fire_agent_notification(
            "new_report",
            result.output if isinstance(result, DeliveryOutput) else rendered,
            product_id=f"{report_title_domain}-{period}",
        )
        return result

    if user_id:
        _try_notify_content_ready(
            user_id=user_id,
            product_type="report",
            title=f"{report_title_domain_display} \u2014 {report_h1_word}",
        )
    _fire_agent_notification("new_report", rendered, product_id=f"{report_title_domain}-{period}")
    return rendered


# ---------------------------------------------------------------------------
# Report internal helpers
# ---------------------------------------------------------------------------

_DOMAIN_THEME_GUIDANCE: dict[str, str] = {
    "medical-research": (
        "clinical applications, treatment outcomes/trials, "
        "reproductive health, drug development, regulatory & policy"
    ),
    "ai-commercial": (
        "product launches, market strategy, funding & acquisitions, "
        "regulatory & compliance, industry partnerships"
    ),
    "financial-intelligence": (
        "market trends, economic indicators, corporate strategy, "
        "regulatory changes, macroeconomic analysis"
    ),
    "tech-ai-developer": (
        "development tools & frameworks, research breakthroughs, "
        "industry adoption, open source & community, AI/ML advancements"
    ),
    "language-learning": (
        "learning methodology, language resources & tools, "
        "proficiency assessment, cultural context, pedagogy research"
    ),
}
_DEFAULT_DOMAIN_GUIDANCE = (
    "technology trends, industry developments, research findings, "
    "policy & regulation, emerging innovations"
)

# Entries are grouped in batches of this size so the LLM prompt stays small
# enough to return reliable JSON even for very long entry lists.
_GROUPING_BATCH_SIZE = 8

# Bounded worker pool for the per-batch grouping LLM calls.  Each call still
# goes through the shared per-provider semaphore (llm.call_with_fallback), so
# provider-level concurrency stays bounded even when the pool is this wide.
_GROUPING_MAX_WORKERS = 4

# Degraded-path (deterministic / chaos-guard fallback) topic target: those
# fallbacks over-split into fine-grained groups, so merge near-duplicates down
# toward 8-12 topics (reassign, never drop).  LLM happy path is untouched.
_GROUPING_TARGET_RANGE: Final[tuple[int, int]] = (8, 12)

# Minimum Jaccard similarity (normalized theme tokens) for the degraded-path
# count-nudge merge: pairs below this are distinct topics and stay separate.
_GROUPING_TARGET_MIN_SIMILARITY: Final[float] = 0.4

# Honest-degradation annotation (issue #120, C4): when grouping degrades (LLM
# fail/timeout, chaos guard, 0/1-group "General" catch-all, or entry-level
# column sections), the rendered product must say so plainly instead of
# silently showing source-type/keyword headings as if they were semantic
# topics.  The marker is pinned byte-for-byte — tests assert the exact string.
_GROUPING_DEGRADATION_MARKER: Final[str] = "> *This edition groups developments by source*"

# Module-level degradation flag: set by ``_log_grouping_degraded`` on every
# degradation path, consumed by ``generate_report`` (after ``_group_by_theme``)
# to annotate the rendered output.  A module attribute (not a return value)
# because degraded grouping happens inside worker batch threads.  Always reset
# before a grouping run so a previous product's degradation cannot leak into
# the next one.
_grouping_degraded: bool = False


# Issue #646: when every LLM call fails the generators still ship a complete
# KB-derived product.  That is correct behaviour, but it is not LLM-generated,
# and reporting L3 for it hides a total model failure as a better result.
# A module attribute (not a return value) because the seams fire inside worker
# threads and helper modules, mirroring ``_grouping_degraded``.
_kb_fallback_reasons: set[str] = set()


def reset_llm_provenance() -> None:
    """Clear the recorded KB-derived fallbacks before a product generation."""
    _kb_fallback_reasons.clear()


def mark_kb_fallback(reason: str) -> None:
    """Record that a KB-derived fallback replaced LLM output."""
    _kb_fallback_reasons.add(reason)


def llm_provenance() -> dict[str, Any]:
    """Return the provenance of the most recent product generation.

    ``llm_generated`` is False as soon as any KB-derived fallback fired, which
    is the signal "this artifact is structurally valid but was not produced by
    the model".
    """
    reasons = sorted(_kb_fallback_reasons)
    return {"llm_generated": not reasons, "kb_fallback_reasons": reasons}


# Issue #167: source-type group headings must state WHERE content came from,
# never WHAT it is — a semantic-sounding label ("Platform & API News") can
# contradict its rows when e.g. pubmed (type api) papers land in the group.
# Provenance-neutral wording only.
_SOURCE_TYPE_THEME_LABELS: dict[str, str] = {
    "hackernews": "Community & Forum Sources",
    "rss": "Syndicated News Feeds",
    "api": "API & Database Sources",
    "github": "Open-Source Repositories",
    "stack": "Q&A & Forum Sources",
    "pubmed": "PubMed & Life-science Sources",
    "arxiv": "Preprint & Archive Sources",
}


# Bounded smaller-prompt retry budgets for the report synthesis (F3 fix,
# round 1): the configured LLM endpoint returned EMPTY completions for
# synthesis prompts ≳ ~11.9K chars (F3 size sweep: 11,908–12,827 → empty
# 5/5; ≤10,734 → OK).  When the primary call comes back without a usable
# executive summary, the synthesis re-calls with an entries-detail block
# condensed to these budgets so the total prompt lands near ~5–7K chars.

# Round-2 (F3 re-verification): the endpoint's empty-completion behavior is
# no longer size-gated — bad windows (~40–60 min) return genuine empty
# completions at ALL prompt sizes, including the condensed ~5.9–6.1K retry
# prompt (0/11 probes).  So the single retry became a bounded multi-attempt
# loop (attempt 1 = full-size prompt; attempts 2+ = the condensed prompt)
# with a short sleep between attempts — long enough to bridge a flapping
# endpoint window, short enough that one ``generate_report`` still completes.
# Both bounds are injectable for tests (no real sleeps under pytest).

# Budgets for the round-2 dedicated product-sections prompt: a small second
# call (issued only for product families when the base synthesis succeeded
# but the parsed result lacks the §2.4 sections) that carries the produced
# executive summary + findings (bounded) so the total stays ~2–3.5K chars,
# far below any prompt-size concern.


#: Sentence ``_render_empty_report`` emits for a no-curated-data report.
_NO_DATA_REPORT_MARKER = "This edition has no curated items yet"


# ---------------------------------------------------------------------------
# LLM-based translation (F10)
# ---------------------------------------------------------------------------

_TRANSLATION_SYSTEM_PROMPT = get_prompt("translation_system")


def _build_translation_prompt(
    title: str,
    body: str,
    target_lang: str,
    domain: str = "",
) -> str:
    """Build the user prompt for translation, optionally injecting terminology guardrails.

    When *domain* is non-empty and a ``knowledge/<domain>/_terminology.yaml``
    file exists, ``do_not_translate`` terms and ``preferred`` translations
    are injected as guardrails into the prompt.
    """
    prompt_parts: list[str] = [
        f"Target language: {target_lang}\n\n",
        f"Title: {title}\n\n",
        f"Body:\n{body}\n\n",
        "Translate the title and body above into the target language. "
        "Preserve all medical terminology, drug names, procedures, "
        "statistics, and citations exactly. Return valid JSON.\n",
    ]

    if domain:
        from autoinfo.terminology import load_terminology  # noqa: PLC0415

        terminology = load_terminology(domain)
        if terminology.terms:
            do_not_translate = [
                t for t, e in terminology.terms.items() if e.type == "do_not_translate"
            ]
            preferred = {
                t: e.preferred
                for t, e in terminology.terms.items()
                if e.type == "preferred" and e.preferred
            }
            if do_not_translate:
                prompt_parts.append(
                    f"The following terms MUST NOT be translated: {', '.join(do_not_translate)}.\n"
                )
            if preferred:
                lines = [f"  {term} → {trans}" for term, trans in preferred.items()]
                prompt_parts.append("Use these preferred translations:\n" + "\n".join(lines) + "\n")

    return "".join(prompt_parts)


def _call_llm_for_translation(
    title: str,
    body: str,
    target_lang: str,
    config: Config | None = None,
    domain: str = "",
) -> dict[str, str]:
    """Translate *title* and *body* into *target_lang* via LiteLLM.

    Returns a dict with ``translated_title`` and ``translated_body``.
    Returns empty strings on failure.
    """
    if config is None:
        config_path = get_config_path()
        if config_path is not None:
            try:
                config = load_config(config_path)
            except Exception:
                config = Config()
        else:
            config = Config()

    model = config.llm.resolve_model()
    full_model = model

    user_prompt = _build_translation_prompt(
        title=title,
        body=body,
        target_lang=target_lang,
        domain=domain,
    )

    try:
        response = call_with_fallback(
            model=full_model,
            messages=[
                {"role": "system", "content": _TRANSLATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            json_mode=config.llm.json_mode and not config.llm.reasoning_model,
            max_tokens=8000,
            temperature=0.1,
            api_key=config.llm.api_key or None,
            base_url=config.llm.base_url or None,
        )
    except Exception as exc:
        logger.error("LLM translation failed: %s", exc)
        return {"translated_title": "", "translated_body": ""}

    content: str = response.choices[0].message.content or ""
    parsed = _parse_json_response(content)
    return {
        "translated_title": parsed.get("translated_title", ""),
        "translated_body": parsed.get("translated_body", ""),
    }


def localize_content(
    content_id: str | None = None,
    content: str | None = None,
    source_lang: str = "",
    target_lang: str = "",
    domain: str = "",
) -> dict[str, Any]:
    """Translate a KB entry or raw text into *target_lang*.

    Two modes:

    **Content-ID mode** (reads from KB, stores translation)::

        result = localize_content(
            content_id="kb-entry-001",
            target_lang="zh",
        )

    **Direct content mode** (no storage, returns translation)::

        result = localize_content(
            content="Hello world",
            source_lang="en",
            target_lang="fr",
        )

    Parameters
    ----------
    content_id:
        KB entry ID to translate.  The entry must exist in the KB store.
    content:
        Raw text to translate directly (no KB lookup).
    source_lang:
        Source language code (e.g. ``"en"``, ``"zh"``).  Required for
        direct-content mode; optional for content-ID mode (auto-detected
        from the KB entry's ``language`` field).
    target_lang:
        Target language code (e.g. ``"zh"``, ``"fr"``, ``"ja"``).
        **Required**.
    domain:
        Domain name (e.g. ``"medical-research"``).  When provided, loads
        domain-specific terminology guardrails from
        ``knowledge/<domain>/_terminology.yaml`` into the translation
        prompt.  When empty in content-ID mode, the domain is inferred
        from the KB entry's metadata.

    Notes
    -----
    Single-entry explicit lookup: the caller names the exact content ID
    (or provides raw text), so the end-user ``content_preference`` tier
    policy is **not applicable** here.  This is an operator tool, not a
    personalized end-user output path — preference-based filtering
    intentionally does not apply.

    Returns
    -------
    dict
        Keys:
        - ``translated_title`` — translated title (empty if direct content)
        - ``translated_body`` — translated text
        - ``target_lang`` — language code used
        - ``source_lang`` — detected or provided source language
        - ``file_path`` — path to stored translation file (content-ID mode only)
        - ``success`` — whether translation succeeded

    Raises
    ------
    ValueError
        If the required parameters are missing or *target_lang* is empty.
    """
    if not target_lang:
        raise ValueError("target_lang is required")

    if content_id:
        from autoinfo.kb import KBStore  # noqa: PLC0415

        store = KBStore()
        entry = store.get_entry(content_id)
        if entry is None:
            raise ValueError(f"KB entry '{content_id}' not found")

        resolved_domain = domain or entry.get("domain", "")
        src_lang = source_lang or entry.get("language", "en")

        file_path_str = entry.get("file_path", "")
        body = ""
        if file_path_str:
            fp = Path(file_path_str)
            if fp.is_file():
                raw = fp.read_text(encoding="utf-8")
                if raw.startswith("---"):
                    end_idx = raw.find("---", 3)
                    if end_idx != -1:
                        body = raw[end_idx + 3 :].strip()
                    else:
                        body = raw
                else:
                    body = raw

        result = _call_llm_for_translation(
            title=entry.get("title", ""),
            body=body,
            target_lang=target_lang,
            domain=resolved_domain,
        )

        if not result.get("translated_title") and not result.get("translated_body"):
            return {
                "success": False,
                "error": "LLM translation returned empty result",
                "content_id": content_id,
                "target_lang": target_lang,
                "source_lang": src_lang,
            }

        translated_file_path = _write_translated_file(entry, result, src_lang, target_lang)

        return {
            "success": True,
            "translated_title": result.get("translated_title", ""),
            "translated_body": result.get("translated_body", ""),
            "target_lang": target_lang,
            "source_lang": src_lang,
            "file_path": str(translated_file_path) if translated_file_path else "",
            "content_id": content_id,
        }

    if content is not None:
        if not source_lang:
            raise ValueError("source_lang is required for direct content translation")
        result = _call_llm_for_translation(
            title="",
            body=content,
            target_lang=target_lang,
            domain=domain,
        )

        if not result.get("translated_body"):
            return {
                "success": False,
                "error": "LLM translation returned empty result",
                "target_lang": target_lang,
                "source_lang": source_lang,
            }

        return {
            "success": True,
            "translated_title": result.get("translated_title", ""),
            "translated_body": result.get("translated_body", ""),
            "target_lang": target_lang,
            "source_lang": source_lang,
        }

    raise ValueError("Either content_id or content must be provided")


def _write_translated_file(
    entry: dict[str, Any],
    translation: dict[str, str],
    source_lang: str,
    target_lang: str,
) -> Path | None:
    """Write the translated Markdown file alongside the original KB entry.

    Creates: ``knowledge/<domain>/<tier>/<topic>/<date>-<slug>.<lang>.md``

    Returns the path to the written file, or ``None`` on failure.
    """
    from datetime import datetime, timezone  # noqa: PLC0415

    original_path = entry.get("file_path", "")
    if not original_path:
        return None

    orig = Path(original_path)
    if not orig.is_file():
        return None

    translated_path = orig.with_name(f"{orig.stem}.{target_lang}{orig.suffix}")

    raw = orig.read_text(encoding="utf-8")
    frontmatter: dict[str, Any] = {}
    body = raw
    if raw.startswith("---"):
        end_idx = raw.find("---", 3)
        if end_idx != -1:
            fm_raw = raw[3:end_idx]
            import yaml  # noqa: PLC0415

            frontmatter = yaml.safe_load(fm_raw) or {}
            body = raw[end_idx + 3 :].strip()

    frontmatter["translated_from"] = source_lang
    frontmatter["translated_to"] = target_lang
    frontmatter["translated_at"] = datetime.now(timezone.utc).isoformat()
    frontmatter["original_entry_id"] = entry.get("entry_id", "")
    frontmatter["original_file"] = str(orig)

    translated_title = translation.get("translated_title", "")
    if translated_title:
        frontmatter["title"] = translated_title

    translated_body = translation.get("translated_body", body)

    full_content = (
        "---\n"
        f"{yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)}"
        "---\n\n"
        f"{translated_body}"
    )
    translated_path.write_text(full_content, encoding="utf-8")
    return translated_path


# ---------------------------------------------------------------------------
# Tutorial generation
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Report / Digest audience adaptation (structured prompt sections)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Report type prompts — specialized section structures per report type
# ---------------------------------------------------------------------------

_REPORT_TYPE_PROMPTS: dict[str, str] = {
    "standard": "",
    "industry": (
        "Structure this report with sections: Industry Overview, "
        "Key Developments, Regulatory Landscape, Competitive Dynamics, "
        "Outlook. Focus on domain-specific trends (e.g. clinical trials "
        "for medical, earnings for financial, funding rounds for tech)."
    ),
    "competitive": (
        "Structure this report with sections: Market Players, "
        "Head-to-Head Comparison (organize into comparison tables by "
        "feature/offering), Strengths & Weaknesses, Strategic Moves, "
        "Market Share Analysis. Extract entity names and compare them "
        "explicitly."
    ),
    "trend": (
        "Structure this report with sections: Trend Overview, Timeline "
        "of Developments (chronological), Change Detection (what changed "
        "in the last N months), Momentum Indicators, Forward-Looking "
        "Signals. Focus on time-based patterns and trajectory."
    ),
    "daily-briefing": (
        "Structure this briefing with sections: Top Stories (max 5, "
        "priority-ordered by relevance score), Need-to-Know Updates, "
        "Briefing Summary (3 bullet points max). Be concise. Prioritize "
        "high-relevance items (relevance_score > 50)."
    ),
    "column": (
        "Structure this column with sections: The Big Idea (single-theme "
        "thesis in an expert persona voice), Deep Dive (longer-form analysis "
        "with evidence, sources, and nuance), What Changed This Week (weekly "
        "cadence — timeline of developments in the period), Implications & "
        "Outlook, Reader Takeaways. Write in a confident expert persona with "
        "analytical depth; this is a longer-form premium column, not a "
        "briefing. Prioritize high-relevance items (relevance_score > 50).\n"
        "The Deep Dive section MUST contain 8-10 distinct subsections "
        "(numbered or headed), each with 2-3 paragraphs of analysis grounded "
        "in specific entries — quote concrete numbers, dates, and named "
        "companies/studies from the source material; no filler paragraphs. "
        "Target total column length 2000-3000 words."
    ),
}

_VALID_REPORT_TYPES: list[str] = list(_REPORT_TYPE_PROMPTS.keys())

# Product-family synthesis sections appended to the report-synthesis prompt
# (spec §2.4, todo 7), keyed by the resolved product family so the default
# ``report`` family stays unchanged. ``implications`` / ``risks`` /
# ``action_required`` are index-aligned 1:1 with ``key_findings`` (spec
# §5.2-5.4 per-takeaway pairing); ``key_metrics`` is enterprise-only.
# The ``|``-delimited line formats below are parsed by
# :func:`_parse_report_markdown` into ``{title, likelihood, impact,
# mitigation}`` / ``{metric, value, source}`` dicts.
_REPORT_PRODUCT_BASE_SECTIONS = (
    "Additionally, append these product sections with exactly one item per "
    "Key Finding bullet, index-aligned 1:1 (item N corresponds to Key "
    "Finding N):\n\n"
    "## Implications\n"
    "- <implication for finding 1>\n"
    "- <implication for finding 2>\n\n"
    "## Risks & Opportunities\n"
    "- <risk title> | <likelihood> | <impact> | <mitigation>\n"
    "(one bullet per finding, same order; likelihood/impact values: "
    "High/Medium/Low)\n"
    "Every risk title MUST embed a concrete number, case, or named entity "
    "from the source entries — no generic labels like 'Valuation Bubble "
    "Risk'. Examples: 'Fintech down-rounds up 3.2x YoY (CB Insights)', "
    "'Stripe API latency 2.1s in APAC peak'. The mitigation MUST name a "
    "specific action, who does it, and a timeline (e.g. 'Switch 30% of "
    "traffic to the fallback provider by 2026-09-30').\n\n"
    "## Action Required\n"
    "- <action for finding 1>\n"
    "- <action for finding 2>\n"
    "(index-aligned with Key Findings; each action MUST specify WHO does it, "
    "WHAT specifically, and a WHEN timeline — e.g. 'CMO: ship the Q3 pricing "
    "experiment to 10% of enterprise customers by 2026-09-15'. Never a bare "
    "'conduct market analysis'.)\n"
    "Each action MUST also name a concrete object (WHICH entity, product, "
    "model, company, or metric the action targets) and a timeframe or trigger "
    "(WHEN it happens — a date, a milestone, or a real-world trigger event). "
    "A bare single-line verb like 'Track AI model releases', 'Monitor "
    "developments', or 'Reassess the market' carries no object and no WHEN — "
    "it is forbidden.  Prefer e.g. 'Track OpenAI GPT-5 benchmark results "
    "against internal evaluation needs by 2026-09-30' or 'Monitor Stripe "
    "latency SLO breaches; reassess the primary provider when p95 exceeds "
    "800ms'.\n\n"
    "The Executive Summary's opening coverage sentence MUST name exactly the "
    'number of Key Findings you detail below — e.g. "This briefing details N '
    'selected items from the period." Never state a coverage count larger '
    "than the number of Key Findings bullets you actually write."
)

_REPORT_ENTERPRISE_METRICS_SECTION = (
    "\n\n## Key Metrics\n"
    "- <metric> | <value> | <source>\n"
    "(quantified metrics from the entries only; one bullet per metric; "
    "source names the entry, study, or dataset)"
)

_REPORT_PRODUCT_SYNTHESIS_PROMPTS: dict[str, str] = {
    "premium-briefing": _REPORT_PRODUCT_BASE_SECTIONS,
    "magazine-digest": _REPORT_PRODUCT_BASE_SECTIONS,
    "enterprise-briefing": (_REPORT_PRODUCT_BASE_SECTIONS + _REPORT_ENTERPRISE_METRICS_SECTION),
}


# ---------------------------------------------------------------------------
# Tutorial / Presentation audience adaptation (must match report vocab)
# ---------------------------------------------------------------------------


def _filter_stale_entries(
    entries: list[dict[str, Any]],
    domain: str,
    *,
    include_stale: bool = False,
    product: str = "product",
) -> list[dict[str, Any]]:
    """Drop entries older than the domain's freshness threshold (TTL).

    Mirrors the digest staleness filter (F51) so teaching-layer products
    (tutorial/presentation) never silently regenerate from an old corpus
    after a source swap (backup issue #60).

    Returns a NEW list containing only non-stale entries (TTL resolution
    via ``resolve_domain_freshness``: config when present, else
    ``DOMAIN_DEFAULT_TTL_DAYS`` / ``DEFAULT_TTL_DAYS``).
    """
    if include_stale:
        return list(entries)
    from autoinfo.config import resolve_domain_freshness  # noqa: PLC0415

    ttl_days, freshness_threshold = resolve_domain_freshness(domain)

    from autoinfo.kb import calculate_freshness_score  # noqa: PLC0415

    active: list[dict[str, Any]] = []
    excluded = 0
    for entry in entries:
        entry_freshness = calculate_freshness_score(entry, ttl_days)
        entry["freshness_score"] = round(entry_freshness, 4)
        if entry_freshness < freshness_threshold:
            entry["is_stale"] = True
            excluded += 1
        else:
            entry["is_stale"] = False
            active.append(entry)
    if excluded:
        logger.info(
            "Excluded %d stale entries from %s for domain '%s'",
            excluded,
            product,
            domain,
        )
    return active


# ---------------------------------------------------------------------------
# Presentation generation
# ---------------------------------------------------------------------------


# Issue #151: default slide count for the digest-path presentation fallback
# (mirrors the standalone generate_presentation default).
_PRESENTATION_SLIDE_COUNT: Final[int] = 10


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _make_audio_persist_path(domain: str | None) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    domain_slug = domain or "all"
    return str(Path("exports") / domain_slug / "podcast" / f"ep-{ts}.mp3")


def _maybe_persist_audio(mp3_bytes: bytes, persist_path: str | None) -> None:
    if not persist_path:
        return
    try:
        p = Path(persist_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(mp3_bytes)
        logger.info("Audio persisted to %s (%d bytes)", persist_path, len(mp3_bytes))
    except OSError:
        logger.warning("Failed to persist audio to %s", persist_path, exc_info=True)


# Markdown patterns to strip when converting to plain text for TTS.


# ---------------------------------------------------------------------------
# Agent-native JSON-LD output format (F28 / G11)
# ---------------------------------------------------------------------------


def _persist_product_analysis_to_kb(
    store: KBStore,
    link_entries: list[dict[str, Any]],
    product_fields: dict[str, Any],
) -> None:
    """Persist populated product analysis fields to the linked KB entries.

    Called after agent rendering (todo 24, output-quality-mega): when a
    product output (premium-briefing / enterprise-briefing / magazine-digest)
    carries the per-product analysis fields, they are written as JSON
    metadata (``{"product_analysis": {...}}``) onto the KB entries the
    output was generated from, via the existing KB metadata dict path
    (``KBStore.update_entry_metadata`` → ``entries.custom_fields`` SQLite
    column → surfaced by ``KBStore.get_entry`` / MCP ``get_kb_entry``).

    Linkage: entries are matched by ``entry_id`` when present (digest path);
    otherwise by ``source_url`` (report-path agent entries hardcode
    ``entry_id: ""``).

    Backward compatible: when no product field is populated (default
    digest/report), nothing is persisted. Failures are logged and never
    break output generation.
    """
    populated = {
        name: product_fields[name] for name in _PRODUCT_ANALYSIS_FIELDS if product_fields.get(name)
    }
    if not populated:
        return
    metadata = {"product_analysis": populated}
    seen: set[tuple[str, str]] = set()
    for entry in link_entries:
        entry_id = str(entry.get("entry_id") or "")
        source_url = str(entry.get("source_url") or "")
        if not entry_id and not source_url:
            continue
        if (entry_id, source_url) in seen:
            continue
        seen.add((entry_id, source_url))
        try:
            target_id = entry_id
            if not target_id:
                found = store.get_entry_by_source_url(source_url)
                if found is None:
                    continue
                target_id = str(found.get("entry_id") or "")
                if not target_id:
                    continue
            store.update_entry_metadata(target_id, metadata)
        except Exception:
            logger.warning(
                "Failed to persist product analysis metadata for %r — output unaffected",
                entry_id or source_url,
                exc_info=True,
            )


# ---------------------------------------------------------------------------
# Content simplification (E14 — CEFR-level parameterised simplification)
# ---------------------------------------------------------------------------

_VALID_SIMPLIFY_TARGETS: frozenset[str] = frozenset({"A1", "A2", "B1", "B2", "C1"})
_CEFR_RANK: dict[str, int] = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}


def simplify_text(
    content: str,
    target_level: str,
    language: str = "en",
) -> dict[str, Any]:
    """Simplify *content* to a target CEFR reading level using LLM.

    First classifies the original text, then uses LLM to rewrite it at the
    target level, and finally verifies the result with a second CEFR
    classification.

    On LLM failure the original text is returned unchanged with
    ``verified=False`` so callers can inspect the ``.error`` key.

    Parameters
    ----------
    content:
        The text to simplify.  Must not be empty.
    target_level:
        Target CEFR level: ``"A1"``, ``"A2"``, ``"B1"``, ``"B2"``, or
        ``"C1"``.
    language:
        Language code: ``"en"``, ``"zh"``, or ``"ja"`` (default ``"en"``).

    Returns
    -------
    dict
        ``{"simplified": str, "original_level": str, "simplified_level":
        str, "verified": bool}`` plus an ``"error"`` key on failure.
    """
    from autoinfo.cefr import classify_text  # noqa: PLC0415

    lang_names: dict[str, str] = {"en": "English", "zh": "Chinese", "ja": "Japanese"}
    lang_name = lang_names.get(language, "English")

    # --- Validate target_level ------------------------------------------------
    if target_level not in _VALID_SIMPLIFY_TARGETS:
        return {
            "simplified": content,
            "original_level": "unknown",
            "simplified_level": "unknown",
            "verified": False,
            "error": (
                f"Invalid target_level: '{target_level}'. Must be one of A1, A2, B1, B2, C1."
            ),
        }

    if not content or not content.strip():
        return {
            "simplified": "",
            "original_level": "unknown",
            "simplified_level": "unknown",
            "verified": False,
            "error": "Content is empty",
        }

    # --- Classify original ----------------------------------------------------
    original_result = classify_text(content, lang=language)
    original_level: str = original_result.get("cefr_level", "unknown")

    # --- LLM simplification ---------------------------------------------------
    system_prompt = get_prompt("text_simplification_system")

    user_prompt = (
        f"Language: {lang_name}\n"
        f"Target CEFR Level: {target_level}\n\n"
        f"Original Text:\n{content[:5000]}\n\n"
        "Rewrite this text at the target CEFR level. Return only the simplified text."
    )

    # Resolve model config (same pattern as cefr.py).  Issue #195: no
    # hardcoded vendor default — resolve_llm_model raises when unconfigured,
    # the surrounding try degrades to the documented call_with_fallback
    # default (llm.py DEFAULT_MODEL) for config-less backward-compat.
    from autoinfo.config import (  # noqa: PLC0415
        get_config_path,
        load_config,
        resolve_llm_model,
    )

    model = ""
    api_key = ""
    base_url = ""
    try:
        config_path = get_config_path()
        if config_path is not None:
            config = load_config(config_path)
            model = resolve_llm_model(config.llm)
            api_key = config.llm.api_key or ""
            base_url = config.llm.base_url or ""
    except Exception:
        logger.debug("Could not load config for simplify_text", exc_info=True)

    try:
        response = call_with_fallback(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=8000,
            temperature=0.3,
            api_key=api_key or None,
            base_url=base_url or None,
        )
        simplified: str = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("LLM simplification failed: %s", exc)
        return {
            "simplified": content,
            "original_level": original_level,
            "simplified_level": "unknown",
            "verified": False,
            "error": str(exc),
        }

    if not simplified:
        return {
            "simplified": content,
            "original_level": original_level,
            "simplified_level": "unknown",
            "verified": False,
            "error": "LLM returned empty response",
        }

    # --- Verify simplified level ----------------------------------------------
    simplified_result = classify_text(simplified, lang=language)
    simplified_level: str = simplified_result.get("cefr_level", "unknown")

    target_rank = _CEFR_RANK.get(target_level, 0)
    simplified_rank = _CEFR_RANK.get(simplified_level, 0)
    verified: bool = simplified_rank > 0 and target_rank > 0 and simplified_rank <= target_rank

    return {
        "simplified": simplified,
        "original_level": original_level,
        "simplified_level": simplified_level,
        "verified": verified,
    }
