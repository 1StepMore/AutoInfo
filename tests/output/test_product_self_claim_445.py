"""#445 — product self-consistency and synthesis grounding.

Two defect classes reached delivered products in the AC5 review:

* a product whose own summary/header contradicts its body (a briefing that
  says "2 selected items" over one rendered Key Findings bullet), and
* a synthesis that cites a source for something that source never says.

Both are now deterministic.  The heavy machinery lives in
``autoinfo.section_parser`` (self-count / orphan-entity parsing) and
``autoinfo.grounding`` (entity support); the tests here cover the behaviour a
revert would break:

* ``self_count_contradictions`` fires on a contradicting self-count and stays
  silent on every product shape that renders the claimed number, and on prose
  numbers that are not self-counts.
* ``D2FormatIntegrity`` BLOCKS the contradiction and only FLAGS the
  entity-orphan escalation (measured ~27% false-positive rate on real
  output — a rule that wrong-accuses a quarter of shipped products must not
  block delivery).
* Honest hedges are never a defect (#179/#191).
* The templates render no orphan heading for an empty section.
* ``_ground_synthesis_citations`` drops an unsupported citation, keeps a
  supported one, and never touches an honest hedge.
* Both synthesis prompts carry the entity-grounding constraint.
"""

from __future__ import annotations

from typing import Any

from autoinfo.output import (
    ProductTemplate,
    _apply_min_content_guard,
    _build_digest_llm_prompt,
    _ground_synthesis_citations,
    _is_substantive_entry,
    _normalize_digest_product_context,
)
from autoinfo.quality import D2FormatIntegrity
from autoinfo.quality_constraints import SYNTHESIS_ENTITY_GROUNDING_CONSTRAINT
from autoinfo.self_claims import (
    self_claim_orphan_entities,
    self_count_contradictions,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _enterprise_briefing(summary: str, scope: str, findings: list[str]) -> str:
    refs = "\n".join(f"{i + 1}. **Ref {i + 1}** — https://x.com/{i + 1}" for i in range(3))
    bullets = "\n".join(f"- {finding}" for finding in findings)
    return (
        "# b2b — Enterprise Briefing\n"
        "**Domain**: b2b\n"
        "**Generated**: 2026-10-02 00:00 UTC\n"
        "---\n"
        "## Executive Summary\n\n"
        f"{summary}\n\n"
        f"> **Scope**: {scope}\n"
        "## Key Findings\n"
        f"{bullets}\n\n"
        "## References\n"
        f"{refs}\n"
    )


class TestSelfCountContradictions:
    """Given a rendered product, When it states its own size, Then the stated
    number must equal the number of items the same product renders."""

    def test_contradicting_selected_items_is_reported(self) -> None:
        body = _enterprise_briefing(
            "The briefing details 2 selected items from the period.",
            "selected 2 of 25 key findings · 25 source references listed.",
            ["Only one finding actually rendered."],
        )

        defects = self_count_contradictions(body)

        assert any("selected items" in d for d in defects), defects

    def test_scope_line_contradicting_rendered_findings_is_reported(self) -> None:
        body = _enterprise_briefing(
            "This briefing covers the period.",
            "selected 3 of 60 key findings · 60 source references listed.",
            ["Only one finding actually rendered."],
        )

        defects = self_count_contradictions(body)

        assert any("key findings" in d for d in defects), defects
        assert any("60 source references" in d for d in defects), defects

    def test_consistent_briefing_is_silent(self) -> None:
        body = _enterprise_briefing(
            "This briefing covers the period.",
            "selected 2 of 3 key findings · 3 sources.",
            ["Finding one rendered in full.", "Finding two rendered in full."],
        )

        assert self_count_contradictions(body) == []

    def test_number_in_an_entry_summary_is_not_a_self_count(self) -> None:
        """A number about third-party prose is not a claim about the product."""
        body = _enterprise_briefing(
            "This briefing covers the period.",
            "selected 1 of 3 key findings · 3 sources.",
            ["Finding one."],
        ) + (
            "\n| 1 | Mark Twain in 1898 | He wrote an 1898 story that anticipated the internet. |\n"
        )

        assert self_count_contradictions(body) == []

    def test_count_for_an_unrendered_section_is_not_a_contradiction(self) -> None:
        """A column has no Key Findings section, so nothing contradicts it."""
        body = (
            "# b2b — Column\n\n"
            "## The Big Idea\n\n"
            "Three items mattered this week, across 12 sources.\n\n"
            "## Deep Dive\n\n"
            "### Real Section\n\n"
            "Prose.\n"
        )

        assert self_count_contradictions(body) == []

    def test_slides_count_compares_against_slide_headings(self) -> None:
        body = (
            "# Deck\n\n"
            "**Slides**: 10\n\n"
            "## Slide 1: One\n\n- bullet\n- bullet\n\n"
            "## Slide 2: Two\n\n- bullet\n"
        )

        assert self_count_contradictions(body) == []

    def test_rendered_presentation_slide_count_is_consistent(self) -> None:
        """The stated slide count is derived from the slides that render."""
        rendered = ProductTemplate(domain="b2b").render(
            "presentation",
            "md",
            {
                "title": "Deck",
                "topic": "Weekly",
                "domain": "b2b",
                "target_audience": "operators",
                "generated_at": "2026-10-02 00:00 UTC",
                "slides": [
                    {
                        "title": f"Slide {i}",
                        "content": f"Body {i}",
                        "bullets": [f"bullet {i}"],
                        "source_url": f"https://x.com/{i}",
                    }
                    for i in range(1, 4)
                ],
            },
        )

        assert "**Slides**: 3" in rendered
        assert self_count_contradictions(rendered) == []
        result = D2FormatIntegrity().check(
            {"product_type": "PROCESSED", "format": "markdown", "body": rendered, "entries": []}
        )
        assert not result.flagged, result.details


class TestD2SelfClaimGate:
    def test_contradiction_blocks_delivery(self) -> None:
        body = _enterprise_briefing(
            "The briefing details 2 selected items from the period.",
            "selected 2 of 3 key findings · 3 sources.",
            ["Only one finding actually rendered."],
        )

        result = D2FormatIntegrity().check(
            {"product_type": "PROCESSED", "format": "markdown", "body": body, "entries": []}
        )

        assert not result.passed
        assert result.flagged
        assert result.details["action"] == "block"
        assert result.details["self_claim"] == "count_contradiction"
        assert result.details["self_claim_contradictions"]

    def test_consistent_product_passes(self) -> None:
        body = _enterprise_briefing(
            "This briefing covers the period.",
            "selected 2 of 3 key findings · 3 sources.",
            ["Finding one rendered in full.", "Finding two rendered in full."],
        )

        result = D2FormatIntegrity().check(
            {"product_type": "PROCESSED", "format": "markdown", "body": body, "entries": []}
        )

        assert result.passed
        assert not result.flagged

    def test_orphan_entity_escalates_without_blocking(self) -> None:
        """An entity the body never states is flagged, never blocked.

        Calibrated: the rule fires on ~27% of real products, so blocking on it
        would reject a quarter of honest output.
        """
        body = _enterprise_briefing(
            "OpenAI has introduced the Zylotron accelerator, a device no supplied "
            "entry describes, and it undercuts competing suppliers.",
            "selected 2 of 3 key findings · 3 sources.",
            ["Finding one rendered in full.", "Finding two rendered in full."],
        )

        result = D2FormatIntegrity().check(
            {"product_type": "PROCESSED", "format": "markdown", "body": body, "entries": []}
        )

        assert result.passed
        assert result.flagged
        assert result.details["action"] == "flag"
        assert result.details["self_claim"] == "orphan_entity_escalation"
        assert any("Zylotron" in e for e in result.details["self_claim_orphan_entities"])

    def test_honest_hedge_is_never_flagged(self) -> None:
        body = _enterprise_briefing(
            "Revenue by region for the Zylotron accelerator is not disclosed in "
            "the available sources, so this period's split cannot be assessed.",
            "selected 2 of 3 key findings · 3 sources.",
            ["Finding one rendered in full.", "Finding two rendered in full."],
        )

        assert self_claim_orphan_entities(body) == []
        result = D2FormatIntegrity().check(
            {"product_type": "PROCESSED", "format": "markdown", "body": body, "entries": []}
        )
        assert not result.flagged

    def test_raw_product_skips_the_check(self) -> None:
        body = _enterprise_briefing(
            "The briefing details 2 selected items from the period.",
            "selected 2 of 3 key findings · 3 sources.",
            ["Only one finding actually rendered."],
        )

        result = D2FormatIntegrity().check(
            {"product_type": "RAW", "format": "markdown", "body": body, "entries": []}
        )

        assert result.passed

    def test_escalation_reaches_delivery_warnings(self) -> None:
        """A flag that never surfaces is not an escalation."""
        from autoinfo.output import _apply_delivery_gates

        body = _enterprise_briefing(
            "OpenAI has introduced the Zylotron accelerator, a device no supplied "
            "entry describes, and it undercuts competing suppliers.",
            "selected 2 of 3 key findings · 3 sources.",
            ["Finding one rendered in full.", "Finding two rendered in full."],
        )

        delivery = _apply_delivery_gates(
            body,
            "markdown",
            [],
            {"product_type": "PROCESSED"},
            "PROCESSED",
            delivery_gate_configs={"D1": {"enabled": False}, "D3": {"enabled": False}},
        )

        assert not delivery.delivery_blocked
        assert any("Zylotron" in w for w in delivery.warnings), delivery.warnings


class TestTemplatesRenderNoOrphanSection:
    """A section with nothing to say must not leave a heading behind."""

    def _pt(self) -> ProductTemplate:
        return ProductTemplate(domain="b2b")

    def _sections(self) -> list[dict[str, Any]]:
        return [
            {
                "title": "Real Section",
                "content": "Real prose about the week.",
                "entries": [{"title": "A story", "summary": "s", "source_url": "https://x.com/1"}],
            },
            {"title": "Orphan Section", "content": "", "entries": []},
        ]

    def _base_context(self) -> dict[str, Any]:
        return {
            "title": "t",
            "domain": "b2b",
            "generated_at": "2026-10-02 00:00 UTC",
            "collection_id": "",
            "executive_summary": "Sum.",
            "sections": self._sections(),
            "references": [{"title": "A story", "source_url": "https://x.com/1"}],
            "implications": [],
            "action_required": [],
            "recommendations": [],
            "appendices": [],
            "key_findings": [{"text": "kf", "source_url": "https://x.com/1"}],
        }

    def test_column_omits_the_empty_section(self) -> None:
        rendered = self._pt().render("column", "md", self._base_context())

        assert "### Real Section" in rendered
        assert "Orphan Section" not in rendered

    def test_report_omits_the_empty_section(self) -> None:
        rendered = self._pt().render("report", "md", self._base_context())

        assert "### Real Section" in rendered
        assert "Orphan Section" not in rendered

    def test_tutorial_omits_the_empty_content_section(self) -> None:
        rendered = self._pt().render(
            "tutorial",
            "md",
            {
                "title": "t",
                "domain": "b2b",
                "generated_at": "2026-10-02 00:00 UTC",
                "collection_id": "",
                "target_audience": "devs",
                "duration": "10 minutes",
                "prerequisites": "None",
                "summary": "This tutorial covers things.",
                "objectives": ["- learn"],
                "content": [
                    {"heading": "Real", "body": "Body text.", "key_takeaway": "kt"},
                    {"heading": "Orphan", "body": "", "key_takeaway": ""},
                ],
                "vocabulary": ["- vocab"],
                "grammar": ["- g"],
                "further_reading": ["- f"],
                "exercises": ["- e"],
            },
        )

        assert "### Real" in rendered
        assert "### Orphan" not in rendered

    def test_container_headings_are_omitted_when_every_child_is_empty(self) -> None:
        """``## Sections`` / ``## Content`` / ``## Deep Dive`` are headings too."""
        context = self._base_context()
        context["sections"] = [{"title": "Empty", "content": "", "entries": []}]

        for product in ("column", "report"):
            rendered = self._pt().render(product, "md", context)
            assert "## Deep Dive" not in rendered, product
            assert "## Sections" not in rendered, product

        tutorial = self._pt().render(
            "tutorial",
            "md",
            {
                "title": "t",
                "domain": "b2b",
                "generated_at": "2026-10-02 00:00 UTC",
                "collection_id": "",
                "target_audience": "devs",
                "duration": "10 minutes",
                "prerequisites": "None",
                "summary": "This tutorial covers things.",
                "objectives": ["- learn"],
                "content": [{"heading": "Empty", "body": "", "key_takeaway": ""}],
                "vocabulary": ["- vocab"],
                "grammar": ["- g"],
                "further_reading": ["- f"],
                "exercises": ["- e"],
            },
        )

        assert "## Content" not in tutorial
        assert "### Empty" not in tutorial

    def test_magazine_never_renders_an_empty_publication_label(self) -> None:
        rendered = self._pt().render(
            "magazine-digest",
            "md",
            {
                "title": "t",
                "domain": "b2b",
                "generated_at": "2026-10-02 00:00 UTC",
                "period_label": "Weekly",
                "date_from": "2026-09-25",
                "date_to": "2026-10-02",
                "llm_synthesis": {},
                "entries": [
                    {
                        "title": "Story one",
                        "summary": "s",
                        "source_url": "https://x.com/1",
                        "source_label": "TechCrunch",
                        "source_platform": "techcrunch",
                    },
                    {
                        "title": "Story two",
                        "summary": "s",
                        "source_url": "",
                        "source_label": "",
                        "source_platform": "",
                    },
                ],
            },
        )

        assert "- ****" not in rendered
        assert "- **General**" in rendered
        assert "## General" in rendered
        assert not any(line.strip() == "-" for line in rendered.splitlines())


class TestSynthesisCitationGrounding:
    _ENTRIES: list[dict[str, Any]] = [
        {
            "title": "A guide to 6th grade math topics",
            "summary": "Fractions, decimals and ratios for sixth graders.",
            "source_url": "https://example.com/math",
        },
        {
            "title": "Duolingo scales its AI tutoring rollout",
            "summary": "Duolingo said it will roll out AI tutoring to enterprise customers.",
            "source_url": "https://example.com/duo",
        },
    ]

    def test_unsupported_citation_is_dropped(self) -> None:
        text = (
            "Duolingo's scalability and enterprise implementation were confirmed by "
            "independent reviewers of grade-school ratios and fractions "
            "(Source: https://example.com/math)."
        )

        assert _ground_synthesis_citations(text, self._ENTRIES) == ""

    def test_supported_citation_is_kept(self) -> None:
        text = (
            "Duolingo will roll out AI tutoring to enterprise customers this year "
            "(Source: https://example.com/duo)."
        )

        assert _ground_synthesis_citations(text, self._ENTRIES) == text

    def test_honest_hedge_is_kept(self) -> None:
        text = (
            "Duolingo revenue by region is not disclosed in the available sources "
            "(Source: https://example.com/duo)."
        )

        assert _ground_synthesis_citations(text, self._ENTRIES) == text

    def test_uncited_prose_is_untouched(self) -> None:
        text = "Plain prose sentence without any citation at all here."

        assert _ground_synthesis_citations(text, self._ENTRIES) == text

    def test_unresolvable_citation_is_untouched(self) -> None:
        text = "Some claim about widgets (Source: https://not-an-entry.example.com/x)."

        assert _ground_synthesis_citations(text, self._ENTRIES) == text

    def test_digest_context_drops_the_unsupported_citation(self) -> None:
        context: dict[str, Any] = {
            "title": "t",
            "domain": "english-learning",
            "generated_at": "2026-10-02",
            "entries": list(self._ENTRIES),
            "llm_synthesis": {
                "executive_summary": (
                    "Duolingo will roll out AI tutoring to enterprise customers "
                    "(Source: https://example.com/duo). English language learning "
                    "at scale was confirmed by reviewers of grade-school ratios "
                    "(Source: https://example.com/math)."
                ),
                "key_findings": [
                    {"text": "Duolingo expands", "source_url": "https://example.com/duo"}
                ],
                "recommendations": ["Keep watching."],
            },
        }

        flat = _normalize_digest_product_context(context, "english-learning")

        assert "grade-school ratios" not in flat["executive_summary"]
        assert "roll out AI tutoring" in flat["executive_summary"]


class TestSynthesisPromptConstraint:
    def test_digest_prompt_carries_the_entity_constraint(self) -> None:
        prompt = _build_digest_llm_prompt([{"title": "A", "summary": "s"}], product_family="column")

        assert SYNTHESIS_ENTITY_GROUNDING_CONSTRAINT in prompt

    def test_default_digest_prompt_carries_the_entity_constraint(self) -> None:
        prompt = _build_digest_llm_prompt([{"title": "A", "summary": "s"}])

        assert SYNTHESIS_ENTITY_GROUNDING_CONSTRAINT in prompt


class TestInputAdequacyGate:
    """#446: entries that exist but carry nothing must not reach synthesis.

    A domain whose entire knowledge base is one synthetic tier-matrix fixture
    (``summary: ''`` on a reserved test host) passes a ``if not entries`` check.
    Against the authoritative store (``autoinfo.db``) this blocks 1 of 23
    domains -- ``default``, whose only entries are the literal rows ``x`` and
    ``y``. An earlier "9 domains / 72 products" figure came from reading the
    ``knowledge/`` file tree instead of the database the pipeline reads, and is
    withdrawn.
    """

    def test_real_entry_is_substantive(self) -> None:
        assert _is_substantive_entry(
            {
                "title": "A Systematic Assessment of In Vitro Fertilization",
                "summary": "x" * 115,
                "source_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed",
            }
        )

    def test_provenance_alone_is_enough_for_a_terse_title(self) -> None:
        """A short title passes on provenance, not on its length."""
        assert _is_substantive_entry(
            {"title": "Entry 1", "summary": "", "source_url": "https://example.com"}
        )

    def test_terse_title_with_no_provenance_and_no_summary_is_not_substantive(self) -> None:
        """The shape the title-length rule got wrong.

        A 7-character title is not evidence of junk: the fixtures in
        tests/delivery carry exactly this and must ship. But with no
        ``source_url`` and no summary there is nothing to report on either."""
        assert not _is_substantive_entry({"title": "Entry 1", "summary": "", "source_url": ""})

    def test_tier_matrix_fixture_is_not_substantive(self) -> None:
        assert not _is_substantive_entry(
            {
                "title": "KB Tier Matrix b2b Raw",
                "summary": "",
                "source_url": "https://kb-tier-matrix.autoinfo.dev/b2b/raw",
            }
        )

    def test_spaced_fixture_title_is_matched_not_just_the_hyphenated_url(self) -> None:
        assert not _is_substantive_entry(
            {"title": "KB Tier Matrix gaming Raw", "summary": "", "source_url": ""}
        )

    def test_synthetic_host_alone_disqualifies_a_fleshed_out_entry(self) -> None:
        assert not _is_substantive_entry(
            {
                "title": "A Plausible Looking Headline",
                "summary": "y" * 200,
                "source_url": "https://kb-tier-matrix.autoinfo.dev/b2b/raw",
            }
        )

    def test_min_content_guard_blocks_zero_substantive_entries(self) -> None:
        from autoinfo.output import DeliveryOutput

        result = DeliveryOutput(output="")
        out = _apply_min_content_guard(
            result,
            [{"title": "KB Tier Matrix b2b Raw", "summary": "", "source_url": "https://x.dev"}],
            "PROCESSED",
        )
        assert out.delivery_blocked is True
        assert any("substantive source material" in w for w in out.warnings)

    def test_min_content_guard_still_ships_real_material(self) -> None:
        from autoinfo.output import DeliveryOutput

        result = DeliveryOutput(output="")
        out = _apply_min_content_guard(
            result,
            [
                {
                    "title": "Real Study",
                    "summary": "z" * 120,
                    "source_url": "https://eutils.ncbi.nlm.nih.gov",
                }
            ],
            "PROCESSED",
        )
        assert out.delivery_blocked is False

    def test_raw_products_are_exempt(self) -> None:
        from autoinfo.output import DeliveryOutput

        result = DeliveryOutput(output="")
        out = _apply_min_content_guard(result, [], "RAW")
        assert out.delivery_blocked is False
