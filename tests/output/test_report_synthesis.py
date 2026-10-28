"""Report/digest synthesis provenance tests (backup issue #207).

The report synthesis once re-slugged a real TechCrunch URL
(``…/launching-new-1-1b-fund/``, HTTP 200) into a fabricated
``…/a16z-brings-growth-fund-to-8-5b-days-after-launching-a-new-1-1b-fund/``
(with ``a-``, HTTP 404) that quality_gate C5 only caught post-hoc, so the
product shipped an untraceable URL.

Issue #207 adds two defenses, both tested here:
1. the synthesis prompts (report + digest) now force every ``(Source: URL)``
   to be taken VERBATIM from the KB Entries list;
2. ``_sanitize_report_urls`` — the deterministic report-family URL whitelist
   backstop (mirror of the #93/#101 presentation sanitizer) — drops any
   body-citation URL that is NOT verifiable against the real KB source_url
   set, so a fabricated slug never reaches a render.
"""

from __future__ import annotations

from autoinfo.output import (
    _build_digest_llm_prompt,
    _build_report_synthesis_prompt,
    _sanitize_report_urls,
)
from autoinfo.quality_constraints import URL_VERBATIM_CONSTRAINT

# The exact fabricated 404 variant from issue #207 (with "a-").
_FABRICATED_404_URL = (
    "https://techcrunch.com/2026/08/31/a16z-brings-growth-fund-to-8-5b-days-"
    "after-launching-a-new-1-1b-fund/"
)
# The real KB/source URL the report should have cited (HTTP 200).
_REAL_KB_URL = "https://techcrunch.com/2026/08/31/launching-new-1-1b-fund/"


class TestReportUrlWhitelistSanitizer:
    """Issue #207 backstop: a fabricated re-slugged URL is dropped."""

    _WHITELIST = {_REAL_KB_URL}

    def test_strips_fabricated_404_variant_keeps_kb_url(self) -> None:
        text = (
            "A16Z's new fund (Source: " + _FABRICATED_404_URL + ") marks a shift. "
            "(Source: " + _REAL_KB_URL + ")"
        )
        cleaned = _sanitize_report_urls(text, self._WHITELIST)
        assert _FABRICATED_404_URL not in cleaned
        assert _REAL_KB_URL in cleaned

    def test_strips_fabricated_citation_whole(self) -> None:
        text = "- Growth-stage push (Source: " + _FABRICATED_404_URL + ")"
        assert _sanitize_report_urls(text, self._WHITELIST) == ("- Growth-stage push ")

    def test_preserves_real_kb_urls(self) -> None:
        text = "The round is live. (Source: " + _REAL_KB_URL + ")"
        assert _sanitize_report_urls(text, self._WHITELIST) == text

    def test_allows_same_article_variants_per_c5(self) -> None:
        # A trailing-slash / full-form variant that only differs AFTER the KB
        # URL's path boundary is the same article (C5-aligned) and survives.
        full = "https://techcrunch.com/2026/08/31/launching-new-1-1b-fund/?utm_source=autoinfo"
        text = "(Source: " + full + ")"
        assert _REAL_KB_URL in _sanitize_report_urls(text, self._WHITELIST)

    def test_strips_fabricated_markdown_link_url(self) -> None:
        text = "[Fund round](%s)" % _FABRICATED_404_URL
        cleaned = _sanitize_report_urls(text, self._WHITELIST)
        assert _FABRICATED_404_URL not in cleaned
        assert "Fund round" in cleaned  # label survives, untraceable URL gone

    def test_preserves_markdown_link_to_real_kb_url(self) -> None:
        text = "[Fund round](%s)" % _REAL_KB_URL
        assert _sanitize_report_urls(text, self._WHITELIST) == text

    def test_strips_sources_plural_with_fabricated_url(self) -> None:
        text = "Trend (Sources: %s and %s)" % (_REAL_KB_URL, _FABRICATED_404_URL)
        cleaned = _sanitize_report_urls(text, self._WHITELIST)
        assert _FABRICATED_404_URL not in cleaned

    def test_plain_text_unchanged(self) -> None:
        assert _sanitize_report_urls("Just narrative text", self._WHITELIST) == (
            "Just narrative text"
        )


class TestReportSynthesisPromptConstraint:
    """Issue #207 prompt constraint: (Source: URL) must be VERBATIM."""

    def test_report_prompt_carries_verbatim_constraint(self) -> None:
        prompt = _build_report_synthesis_prompt(
            "[Entry 1]\nTitle: x\nSummary: y\nSource URL: " + _REAL_KB_URL
        )
        assert URL_VERBATIM_CONSTRAINT in prompt

    def test_digest_prompt_carries_verbatim_constraint(self) -> None:
        prompt = _build_digest_llm_prompt(
            [{"title": "x", "summary": "y", "source_url": _REAL_KB_URL, "tags": []}]
        )
        assert URL_VERBATIM_CONSTRAINT in prompt


class TestCitationResidueCleanup:
    """Issue #644: stripping an unverifiable citation must not leave debris.

    Removing ``(Source: <unverifiable>)`` used to leave the surrounding
    commas and spaces behind, so a sentence read ``"all feature , , ."``.
    The residue cleanup is confined to what the removal produced: a
    legitimate comma list elsewhere in the same text is untouched.
    """

    _WHITELIST = {_REAL_KB_URL}

    def test_chained_citations_leave_a_single_sentence_end(self) -> None:
        text = (
            "the communication of add-on interventions all feature "
            f"(Source: {_FABRICATED_404_URL}), "
            f"(Source: {_FABRICATED_404_URL}), "
            f"(Source: {_FABRICATED_404_URL})."
        )
        cleaned = _sanitize_report_urls(text, self._WHITELIST)
        assert " , " not in cleaned
        assert ", ," not in cleaned
        assert cleaned.endswith("all feature .") or cleaned.endswith("all feature.")

    def test_citation_between_words_leaves_one_space(self) -> None:
        text = (
            "prenatal second-hand smoke exposure "
            f"(Source: {_FABRICATED_404_URL}) and increased mortality"
        )
        cleaned = _sanitize_report_urls(text, self._WHITELIST)
        assert "exposure  and" not in cleaned
        assert "exposure and increased mortality" in cleaned

    def test_comma_list_elsewhere_is_not_touched(self) -> None:
        text = (
            "Findings cover apples, oranges, pears, and plums. "
            f"One claim (Source: {_FABRICATED_404_URL}) was dropped."
        )
        cleaned = _sanitize_report_urls(text, self._WHITELIST)
        assert "apples, oranges, pears, and plums" in cleaned
        assert "(Source:" not in cleaned

    def test_no_removal_means_no_residue_pass(self) -> None:
        text = "The round is live  and well. (Source: " + _REAL_KB_URL + ")"
        assert _sanitize_report_urls(text, self._WHITELIST) == text
