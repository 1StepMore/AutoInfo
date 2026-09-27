"""#403: the template footer must not be parsed as section content.

Every markdown product template ends with a provenance footer of a uniform
shape — ``*<Product> · <domain> · <generated_at>>*``:

    column.md.j2:130              *Column · {{ domain_display_name(domain) }} · … *
    digest.md.j2:84               *Digest · … *
    enterprise-briefing.md.j2:88  *Enterprise Briefing · … *
    magazine-digest.md.j2:78      *Magazine Digest · … *
    premium-briefing.md.j2:75     *Premium Briefing · … *
    presentation.md.j2:44         *Presentation · … *
    report.md.j2:79               *Report · … *
    tutorial.md.j2:115            *Tutorial · … *

The footer is a plain text line, not a heading, so the block parser files it
as ordinary body text of whatever section happens to be last.  When that
section feeds a canonical D1 key, the canonical value ends with the footer —
e.g. a premium briefing's ``recommendations`` was measured as::

    '- [ ] A3 - [ ] A4 *Premium Briefing · AI Commercial · 2026-09-27 10:00 UTC*'

Measured contamination (real template renders, not inferred):
``premium-briefing`` -> ``recommendations``; ``column``, ``magazine-digest``
and ``presentation`` -> ``key_findings``.  ``enterprise-briefing``,
``report``, ``digest`` and ``tutorial`` are unaffected because their final
section does not feed a canonical key.

This is NOT a D1 pass/fail problem — D1 only tests empty-vs-non-empty, so the
gate verdict is unchanged either way.  The damage is to the *value*: any
product-quality audit, gate report or reviewer reading
``sections["key_findings"]`` / ``["recommendations"]`` sees trailing metadata
it cannot distinguish from content.

The footer must still be present in the rendered product — it is
user-facing provenance.  Only the PARSED SECTION VALUE must exclude it, which
is what these tests pin.  They also pin that a footer-shaped line which is NOT
the document's final line survives, so the rule cannot degenerate into a
blanket "drop anything that looks like a footer".
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from autoinfo.section_parser import _sections_from_headings

#: The uniform footer shape: a fully italic line carrying two ``·`` separators.
#: Deliberately loose about the field CONTENTS (they are product/domain/time)
#: and tight about the structure, because the structure is what all 8
#: templates guarantee.
_FOOTER_SHAPE = re.compile(r"^\*[^*\n]*·[^*\n]*·[^*\n]*\*$")

#: What a contaminated value looks like: a ``*``-delimited italic run with two
#: ``·`` separators glued onto the end of otherwise-normal content.
_TRAILING_FOOTER = re.compile(r"·[^*]*\*\s*$")


def _footerish(value: str) -> bool:
    return bool(_TRAILING_FOOTER.search(value))


def _render(template_name: str, context: dict[str, Any]) -> str:
    from autoinfo.output import _get_jinja_env

    return _get_jinja_env().get_template(template_name).render(context)


def _base() -> dict[str, Any]:
    return {
        "title": "Sample Product",
        "domain": "ai-commercial",
        "generated_at": "2026-09-27 10:00 UTC",
    }


def _ref(i: int = 1) -> dict[str, Any]:
    return {
        "title": f"Ref {i}",
        "source_url": f"https://example.org/{i}",
        "source_type": "api",
        "source_platform": "rss",
        "domain": "ai-commercial",
    }


# ---------------------------------------------------------------------------
# Contexts that reproduce the measured contamination
# ---------------------------------------------------------------------------


def _premium_context() -> dict[str, Any]:
    ctx = _base()
    ctx.update(
        {
            "executive_summary": "MarketShiftBody",
            # 2 findings, 4 risks/actions -> the overflow sections render, so the
            # final rendered section is `## Recommended Actions`, which is the
            # canonical `recommendations` source.
            "key_findings": [
                {"text": "HospitalsAdoptTriageBody", "source_url": "https://example.org/1"},
                {"text": "ReimbursementBlockerBody", "source_url": "https://example.org/2"},
            ],
            "risks": [
                {"title": f"Risk{i}", "likelihood": "Med", "impact": "High", "mitigation": "Plan"}
                for i in (1, 2, 3, 4)
            ],
            "action_required": [f"AuditContractsStep{i}Body" for i in (1, 2, 3, 4)],
        }
    )
    return ctx


def _column_context() -> dict[str, Any]:
    ctx = _base()
    ctx.update(
        {
            "executive_summary": "ColumnBigIdeaBody",
            "sections": [{"title": "DeepDiveTitleMarker", "content": "DeepDiveBodyMarker"}],
            "references": [_ref()],
            "implications": ["ImplicationBody"],
        }
    )
    return ctx


def _magazine_context() -> dict[str, Any]:
    ctx = _base()
    ctx.update(
        {
            "period_label": "Weekly",
            "llm_synthesis": {
                "editorial_intro": "EditorialNoteBody",
                "feature_story": "FeatureBody",
            },
            "entries": [
                {
                    "title": f"StoryTitle{i}Body",
                    "summary": f"StorySummary{i}Body",
                    "source_url": f"https://example.org/{i}",
                    "source_type": "api",
                    "source_platform": "rss",
                    "domain": "ai-commercial",
                }
                for i in (1, 2)
            ],
            "publications": ["TechCrunch"],
        }
    )
    return ctx


def _presentation_context() -> dict[str, Any]:
    ctx = _base()
    ctx.update(
        {
            "audience": "executive",
            "slides": [
                {
                    "title": "SlideOneTitle",
                    "content": "SlideOneBody",
                    "bullet_points": ["BulletBody"],
                },
                {"title": "SlideTwoTitle", "content": "SlideTwoBody"},
                {"title": "SlideThreeTitle", "content": "SlideThreeBody"},
            ],
        }
    )
    return ctx


def _enterprise_context() -> dict[str, Any]:
    ctx = _base()
    ctx.update(
        {
            "executive_summary": "EnterpriseSummaryBody",
            "key_findings": [
                {"text": "EnterpriseFindingOneBody", "source_url": "https://example.org/1"},
                {"text": "EnterpriseFindingTwoBody", "source_url": "https://example.org/2"},
            ],
            "action_required": ["EnterpriseActionBody"],
            "recommendations": ["EnterpriseRecommendationBody"],
            "risks": [
                {
                    "title": "EnterpriseRiskBody",
                    "likelihood": "Med",
                    "impact": "High",
                    "mitigation": "Plan",
                }
            ],
            "references": [_ref()],
        }
    )
    return ctx


def _report_context() -> dict[str, Any]:
    ctx = _base()
    ctx.update(
        {
            "executive_summary": "ReportSummaryBody",
            "key_findings": [
                {"text": "ReportFindingOneBody", "source_url": "https://example.org/1"},
                {"text": "ReportFindingTwoBody", "source_url": "https://example.org/2"},
            ],
            "recommendations": ["ReportRecommendationBody"],
            "references": [_ref()],
        }
    )
    return ctx


#: (template, product_type, expected-canonical-key) for every measured case.
#: ``None`` means "this product must not be contaminated", asserted negatively.
_CASES: list[tuple[str, str, str | None, Any]] = [
    ("premium-briefing.md.j2", "premium_briefing", "recommendations", _premium_context),
    ("column.md.j2", "column", "key_findings", _column_context),
    ("magazine-digest.md.j2", "magazine_digest", "key_findings", _magazine_context),
    ("presentation.md.j2", "presentation", "key_findings", _presentation_context),
    ("enterprise-briefing.md.j2", "enterprise_briefing", None, _enterprise_context),
    ("report.md.j2", "report", None, _report_context),
]


class TestFooterIsNotSectionContent:
    """The core rule: a trailing footer must not reach a canonical value."""

    @pytest.mark.parametrize(
        ("template", "product_type", "canonical", "context_factory"),
        _CASES,
        ids=[c[0] for c in _CASES],
    )
    def test_footer_never_lands_in_a_canonical_value(
        self,
        template: str,
        product_type: str,
        canonical: str | None,
        context_factory: Any,
    ) -> None:
        body = _render(template, context_factory())
        sections = _sections_from_headings(body, product_type)

        for key, value in sections.items():
            assert not _footerish(value), (
                f"{template}: canonical {key!r} carries the template footer: {value!r}"
            )
        if canonical is not None:
            # Guard against the test passing vacuously: the canonical key the
            # measurement blames must actually be present and non-empty.
            assert sections.get(canonical), (
                f"{template}: expected a non-empty {canonical!r}; got {sections!r}"
            )

    @pytest.mark.parametrize(
        ("template", "product_type", "canonical", "context_factory"),
        _CASES,
        ids=[c[0] for c in _CASES],
    )
    def test_footer_is_still_present_in_the_rendered_product(
        self,
        template: str,
        product_type: str,
        canonical: str | None,
        context_factory: Any,
    ) -> None:
        """The footer is user-facing provenance — it must NOT be stripped.

        This is the guard against "fixing" the contamination by deleting the
        footer from the product, which would remove real information.
        """
        body = _render(template, context_factory())
        lines = [line.strip() for line in body.splitlines() if line.strip()]

        assert lines, f"{template}: rendered nothing"
        assert _FOOTER_SHAPE.match(lines[-1]), (
            f"{template}: expected the final rendered line to be the footer, got {lines[-1]!r}"
        )

    def test_measured_premium_contamination_is_reproduced_by_the_fixture(self) -> None:
        """Pin the exact defect text so the fixture cannot silently drift.

        Before the fix this returned the footer-glued value; if the fixture
        ever stops reproducing it, the guard above could pass vacuously.
        """
        body = _render("premium-briefing.md.j2", _premium_context())
        sections = _sections_from_headings(body, "premium_briefing")
        recommendations = sections.get("recommendations", "")

        # Real content survives; only the metadata tail is disallowed.
        assert "AuditContractsStep" in recommendations
        assert not _footerish(recommendations), recommendations


class TestFooterRuleIsNotOverBroad:
    """The rule must key on POSITION as well as shape, not blanket-filter."""

    def test_a_footer_shaped_line_that_is_not_last_is_preserved(self) -> None:
        """Body prose that looks like a footer must NOT be discarded.

        If the implementation matched the shape anywhere in the document it
        would eat legitimate content. Pinning the position requirement is what
        keeps this from degenerating into a blanket filter.
        """
        body = (
            "# Report\n\n"
            "## Key Findings\n"
            "RealFindingBody\n"
            "*Not A Footer · Middle Of Doc · 2026-01-01 00:00 UTC*\n"
            "MoreRealFindingBody\n"
            "\n---\n\n"
            "*Report · AI Commercial · 2026-09-27 10:00 UTC*\n"
        )
        sections = _sections_from_headings(body, "report")

        assert "Not A Footer" in sections["key_findings"], sections
        assert "MoreRealFindingBody" in sections["key_findings"], sections

    def test_a_document_without_a_footer_is_unaffected(self) -> None:
        body = "# Report\n\n## Key Findings\nOnlyFindingBody\n\n## Recommendations\nRecBody\n"
        sections = _sections_from_headings(body, "report")

        assert sections["key_findings"] == "OnlyFindingBody"
        assert sections["recommendations"] == "RecBody"

    def test_a_trailing_horizontal_rule_alone_is_not_a_footer(self) -> None:
        """`---` is a section separator, not metadata — it must stay filterable."""
        body = "# Report\n\n## Key Findings\nRealBody\n\n---\n\n*Report · AI Commercial · 2026*\n"
        sections = _sections_from_headings(body, "report")

        assert sections["key_findings"] == "RealBody"
        assert not _footerish(sections["key_findings"])
