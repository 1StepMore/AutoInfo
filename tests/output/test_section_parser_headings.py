"""#400: section parsing across real-template heading-depth boundaries.

Issue #400: the markdown section splitter cut a block at **any** heading
level, so an H2 whose direct body is empty (``## Key Takeaways`` immediately
followed by ``### 1. ...`` children) registered as an EMPTY section.  Premium
briefings therefore lost ``key_findings`` even though the rendered body
carried the takeaways; digest/tutorial lost nested content likewise.  The
previous regression fixture was HAND-WRITTEN markdown one structural tier
simpler than production, which is exactly why the bug shipped — so these
tests render the REAL Jinja templates through the repo's own environment and
assert on the real rendered output.

The fix makes parsing LEVEL-AWARE as a SUPERSET: every heading remains its
own block, and each block's content also absorbs descendant text until the
next heading of level ``<=`` its own.  Fence awareness is added because
``tutorial.md.j2`` wraps LLM-generated code in a ```python fence.

Import note: these tests import the parser from
``autoinfo.delivery.gate_report`` (the gate path re-exports the canonical
implementation), never ``autoinfo.section_parser`` directly, so they keep
working across the single-sourcing refactor.

All tests are hermetic: real template renders only, no network, no LLM, no
domain, no filesystem writes.
"""

from __future__ import annotations

from typing import Any

import pytest

from autoinfo.delivery.gate_report import _sections_from_headings
from autoinfo.output import _get_jinja_env


def _render(template_name: str, context: dict[str, Any]) -> str:
    """Render one real template through the repo's shared Jinja environment."""
    return _get_jinja_env().get_template(template_name).render(context)


def _base_context() -> dict[str, Any]:
    """Minimal context keys every product template reads unconditionally."""
    return {
        "title": "Sample Product",
        "domain": "ai-commercial",
        "generated_at": "2026-09-27 10:00 UTC",
    }


# ---------------------------------------------------------------------------
# Context builders — one per product family.
# ---------------------------------------------------------------------------


def _premium_context() -> dict[str, Any]:
    """premium-briefing with a *production-shaped* nested H3 takeaway list.

    ``risks``/``action_required`` are longer than ``key_findings`` so the
    template's ``length > _kf_len`` guards actually render
    ``## Risks & Opportunities`` and ``## Recommended Actions`` (#400 note).
    """
    ctx = _base_context()
    ctx.update(
        {
            "executive_summary": "Executive summary body.",
            "key_findings": [
                {"text": "Hospitals adopt AI triage at growing scale"},
                {"text": "Reimbursement codes remain the main blocker"},
            ],
            "implications": ["So what one", "So what two"],
            "risks": [
                {
                    "title": "Regulatory drift",
                    "likelihood": "Medium",
                    "impact": "High",
                    "mitigation": "Lobby",
                },
                {
                    "title": "Vendor lock-in",
                    "likelihood": "Low",
                    "impact": "Medium",
                    "mitigation": "Multi-vendor",
                },
                {
                    "title": "Talent gap",
                    "likelihood": "High",
                    "impact": "High",
                    "mitigation": "Train",
                },
            ],
            "action_required": [
                "Audit vendor contracts",
                "Update reimbursement playbook",
                "Run pilot with two hospitals",
            ],
            "references": [{"title": "Ref One", "source_url": "https://e/1"}],
        }
    )
    return ctx


def _digest_context() -> dict[str, Any]:
    """digest.md with the H2 ``## Executive Summary`` + H3 children shape."""
    ctx = _base_context()
    ctx.update(
        {
            "period_label": "Weekly",
            "date_from": "2026-09-20",
            "date_to": "2026-09-27",
            "llm_synthesis": {
                "executive_summary": "ExecutiveBodyMarker",
                "key_findings": [{"topic": "TopicA", "detail": "FindingBodyMarker"}],
                "trends": ["TrendBodyMarker"],
                "recommendations": ["RecBodyMarker"],
            },
            "entries": [
                {
                    "title": "Entry One",
                    "source_label": "Wired",
                    "source_platform": "rss",
                    "summary": "EntryOneBody",
                    "key_points": ["kp"],
                    "source_url": "https://e/one",
                }
            ],
        }
    )
    return ctx


def _digest_html_context() -> dict[str, Any]:
    """digest.html with ``<h2>Key Findings</h2>`` + ``<h3>`` children."""
    return {
        "title": "Sample Product",
        "domain_name": "ai-commercial",
        "period": "Weekly",
        "generated_at": "2026-09-27 10:00 UTC",
        "executive_summary": "ExecutiveBodyMarker",
        "key_findings": [
            {
                "title": "FindingTitleMarker",
                "text": "FindingBodyMarker",
                "source_url": "https://e/1",
            }
        ],
        "trends": ["TrendBodyMarker"],
        "recommendations": ["RecBodyMarker"],
        "entries": [
            {"title": "Entry One", "summary": "EntryOneBody", "source_url": "https://e/one"}
        ],
    }


def _tutorial_context() -> dict[str, Any]:
    """tutorial.md with ``## Content``/``## Exercises`` + H3 children.

    Each marker is unique so a test can prove *which* section supplied a
    canonical value (the #400 tutorial value-source flip).
    """
    ctx = _base_context()
    ctx.update(
        {
            "target_audience": "engineers",
            "duration": "30 min",
            "prerequisites": "none",
            "collection_id": "",
            "objectives": ["ObjectiveOne"],
            "content": [
                {
                    "heading": "ContentHeadingMarker",
                    "body": "ContentBodyMarker",
                    "code_example": "",
                    "code_language": "",
                    "key_takeaway": "",
                }
            ],
            "vocabulary": [],
            "grammar": [],
            "exercises": [
                {
                    "title": "ExerciseTitleMarker",
                    "description": "ExerciseBodyMarker",
                    "hint": "",
                    "solution": "",
                }
            ],
            "summary": "SummaryBodyMarker",
            "further_reading": ["FurtherReadingMarker"],
            "references": [],
        }
    )
    return ctx


def _fenced_tutorial_context() -> dict[str, Any]:
    """tutorial.md whose ``## Content`` carries a ```python fence body.

    The fence body contains a ``# not a heading`` line and a
    ``## Recommendations`` line — both must stay plain code (#400).
    """
    ctx = _tutorial_context()
    ctx["content"] = [
        {
            "heading": "ContentHeadingMarker",
            "body": "ContentBodyMarker",
            "code_example": "# not a heading\n## Recommendations\nevil = 1\n",
            "code_language": "python",
            "key_takeaway": "",
        }
    ]
    ctx["exercises"] = []
    return ctx


def _report_context() -> dict[str, Any]:
    """report.md: flat canonical H2s plus nested ``## Sections``/``## Appendices``."""
    ctx = _base_context()
    ctx.update(
        {
            "executive_summary": "ReportExecBody",
            "key_findings": [{"text": "ReportFindingBody"}],
            "recommendations": ["ReportRecBody"],
            "sections": [
                {"title": "SectionTitleMarker", "content": "SectionBodyMarker", "entries": []}
            ],
            "references": [{"title": "Ref One", "source_url": "https://e/1"}],
            "appendices": [{"title": "AppendixTitleMarker", "content": "AppendixBodyMarker"}],
        }
    )
    return ctx


def _column_context() -> dict[str, Any]:
    """column.md: ``## Deep Dive`` and ``## Appendices`` gain H3 children."""
    ctx = _base_context()
    ctx.update(
        {
            "executive_summary": "ColumnBigIdeaBody",
            "sections": [
                {"title": "DeepDiveTitleMarker", "content": "DeepDiveBodyMarker", "entries": []}
            ],
            "references": [{"title": "Ref One", "source_url": "https://e/1"}],
            "implications": ["ImplBody"],
            "action_required": [],
            "recommendations": [],
            "appendices": [{"title": "AppendixTitleMarker", "content": "AppendixBodyMarker"}],
        }
    )
    return ctx


def _magazine_context() -> dict[str, Any]:
    """magazine-digest: each ``## {{ publication }}`` cluster has H3 entries."""
    return {
        "title": "Magazine",
        "period_label": "Weekly",
        "domain": "general-news",
        "date_from": "2026-09-20",
        "date_to": "2026-09-27",
        "generated_at": "2026-09-27 10:00 UTC",
        "llm_synthesis": {"executive_summary": "MagExec"},
        "entries": [
            {
                "title": "MagEntryTitleMarker",
                "summary": "MagEntryBody",
                "source_label": "Wired",
                "source_platform": "rss",
                "source_url": "https://m/1",
            }
        ],
    }


def _enterprise_context() -> dict[str, Any]:
    """enterprise-briefing: flat H2 headings only (no H3 children)."""
    ctx = _base_context()
    ctx.update(
        {
            "executive_summary": "EntExecBody",
            "key_findings": [{"text": "EntFindingBody"}],
            "references": [{"title": "Ref One", "source_url": "https://e/1"}],
            "key_metrics": [],
            "action_required": ["EntActionBody"],
            "recommendations": ["EntRecBody"],
            "risks": [],
        }
    )
    return ctx


def _presentation_context() -> dict[str, Any]:
    """presentation.md: flat ``## Slide N:`` headings (slide fallback path)."""
    ctx = _base_context()
    ctx.update(
        {
            "topic": "Topic",
            "target_audience": "exec",
            "slides": [
                {
                    "title": "SlideTitleMarker",
                    "content": "SlideBodyMarker",
                    "bullets": ["bul1"],
                    "source_url": "",
                    "notes": "",
                }
            ],
            "description": "desc",
        }
    )
    return ctx


# ---------------------------------------------------------------------------
# premium-briefing — the #400 core (H2 Key Takeaways -> H3 children).
# ---------------------------------------------------------------------------


class TestPremiumNestedTakeaways:
    """#400: premium ``## Key Takeaways`` must expose its H3 children."""

    def test_real_render_contains_both_guarded_sections(self) -> None:
        """Guard the fixture shape: the render must carry the nested H3 shape
        AND the sibling H2s that the template gates behind ``length > _kf_len``.
        Without this the ``key_findings`` assertion could pass on a fixture
        that never reproduced production (#400)."""
        body = _render("premium-briefing.md.j2", _premium_context())
        assert "## Key Takeaways" in body
        assert "### 1. Hospitals adopt AI triage at growing scale" in body
        assert "## Risks & Opportunities" in body
        assert "## Recommended Actions" in body

    def test_key_takeaways_h3_children_populate_key_findings(self) -> None:
        """#400: the real premium render's ``key_findings`` must be NON-EMPTY
        and carry the actual takeaway text — the H3 heading text lives inside
        the parent H2's span under level-aware parsing.  Before the fix the
        ``## Key Takeaways`` block was empty, so ``key_findings`` was absent."""
        body = _render("premium-briefing.md.j2", _premium_context())
        sections = _sections_from_headings(body, "premium_briefing")
        key_findings = sections.get("key_findings", "")
        assert "Hospitals adopt AI triage at growing scale" in key_findings
        assert "Reimbursement codes remain the main blocker" in key_findings


# ---------------------------------------------------------------------------
# digest.md — Executive Summary grows, key_findings must not regress.
# ---------------------------------------------------------------------------


class TestDigestNestedSections:
    """#400: digest ``## Executive Summary`` absorbs its H3 subsections."""

    def test_executive_summary_stays_source_and_absorbs_children(self) -> None:
        """#400: ``summary`` must STAY sourced from ``## Executive Summary``
        (document order still wins) while its content grows to include the
        nested ``### Key Findings`` / ``### Trends`` / ``### Recommendations``
        bodies.  A pure-absorption parser would have deleted the standalone
        ``### Key Findings`` block and regressed D1 — this pins the superset."""
        body = _render("digest.md.j2", _digest_context())
        sections = _sections_from_headings(body, "digest")
        summary = sections.get("summary", "")
        assert "ExecutiveBodyMarker" in summary
        assert "FindingBodyMarker" in summary
        assert "TrendBodyMarker" in summary
        assert "RecBodyMarker" in summary

    def test_key_findings_standalone_h3_block_survives(self) -> None:
        """#400: the standalone ``### Key Findings`` block must remain its own
        block (superset, not absorption), so ``key_findings`` does not regress
        after the H2 parent starts absorbing the same children."""
        body = _render("digest.md.j2", _digest_context())
        sections = _sections_from_headings(body, "digest")
        assert "FindingBodyMarker" in sections.get("key_findings", "")

    def test_entries_do_not_hijack_summary(self) -> None:
        """#400: ``## Entries`` with ``### N. title`` children must not steal
        the ``summary`` alias — ``## Executive Summary`` precedes it."""
        body = _render("digest.md.j2", _digest_context())
        sections = _sections_from_headings(body, "digest")
        assert "EntryOneBody" not in sections.get("summary", "")


# ---------------------------------------------------------------------------
# digest.html — the HTML path must mirror the markdown tree.
# ---------------------------------------------------------------------------


class TestDigestHtmlNestedSections:
    """#400: the HTML parser path must also keep H3 children of an H2."""

    def test_h2_key_findings_absorbs_h3_children(self) -> None:
        """#400: ``<h2>Key Findings</h2>`` with ``<h3>`` finding children must
        yield NON-EMPTY ``key_findings`` carrying the finding title/body — the
        HTML path previously truncated at the ``<h3>`` boundary, leaving only
        the grid rank marker ``#1`` as content."""
        body = _render("digest.html.j2", _digest_html_context())
        sections = _sections_from_headings(body, "digest")
        key_findings = sections.get("key_findings", "")
        assert key_findings
        assert "FindingTitleMarker" in key_findings
        assert "FindingBodyMarker" in key_findings


# ---------------------------------------------------------------------------
# tutorial.md — the two value-source FLIPS (D1-neutral, pinned explicitly).
# ---------------------------------------------------------------------------


class TestTutorialValueSourceFlips:
    """#400: level-aware parsing flips tutorial canonical value sources."""

    def test_summary_flips_from_summary_to_content(self) -> None:
        """#400: ``summary`` must now come from ``## Content`` (~L24) instead
        of ``## Summary`` (~L91) — the absorbed ``### heading`` child makes
        ``## Content`` the first non-empty ``summary`` alias in document order.
        This is D1-neutral (tutorial does not require ``summary``) but must be
        pinned so a future re-order cannot silently move the value again."""
        body = _render("tutorial.md.j2", _tutorial_context())
        sections = _sections_from_headings(body, "tutorial")
        summary = sections.get("summary", "")
        assert "ContentBodyMarker" in summary
        assert "SummaryBodyMarker" not in summary

    def test_recommendations_flip_from_further_reading_to_exercises(self) -> None:
        """#400: ``recommendations`` must now come from ``## Exercises``
        (~L66) instead of ``## Further Reading`` (~L97), because the absorbed
        ``### Exercise N`` children make ``## Exercises`` win first-match."""
        body = _render("tutorial.md.j2", _tutorial_context())
        sections = _sections_from_headings(body, "tutorial")
        recommendations = sections.get("recommendations", "")
        assert "ExerciseBodyMarker" in recommendations
        assert "FurtherReadingMarker" not in recommendations

    def test_learning_objectives_still_supply_key_findings(self) -> None:
        """#400: ``## Learning Objectives`` has no H3 children, so its
        ``key_findings`` value must be unchanged by the fix (no regression)."""
        body = _render("tutorial.md.j2", _tutorial_context())
        sections = _sections_from_headings(body, "tutorial")
        assert "ObjectiveOne" in sections.get("key_findings", "")


# ---------------------------------------------------------------------------
# Other product families.
# ---------------------------------------------------------------------------


class TestReportSections:
    """#400: report canonical values must be unchanged by nesting."""

    def test_canonical_sections_unchanged(self) -> None:
        """#400: report's explicit ``## Executive Summary`` / ``## Key
        Findings`` / ``## Recommendations`` still win their aliases even though
        ``## Sections`` (with ``### title`` children) now carries content —
        the canonical values must not move to the nested sections."""
        body = _render("report.md.j2", _report_context())
        sections = _sections_from_headings(body, "report")
        assert sections.get("summary", "") == "ReportExecBody"
        assert "ReportFindingBody" in sections.get("key_findings", "")
        assert "ReportRecBody" in sections.get("recommendations", "")
        assert "SectionBodyMarker" not in sections.get("summary", "")


class TestColumnSections:
    """#400: column ``## Deep Dive`` / ``## Appendices`` gain children."""

    def test_column_fallback_captures_deep_dive_children(self) -> None:
        """#400: column's any-content fallback must observe the absorbed
        ``### section.title`` children (``DeepDiveBodyMarker``) — before the
        fix the fallback picked the ``## The Big Idea`` body only."""
        body = _render("column.md.j2", _column_context())
        sections = _sections_from_headings(body, "column")
        key_findings = sections.get("key_findings", "")
        assert key_findings
        assert "DeepDiveBodyMarker" in key_findings


class TestMagazineSections:
    """#400: magazine publication clusters absorb their entry children."""

    @pytest.mark.parametrize("product_type", ["magazine", "magazine_digest"])
    def test_publication_cluster_absorbs_entry_children(self, product_type: str) -> None:
        """#400: every ``## {{ publication }}`` cluster must absorb its
        ``### entry.title`` children, so a magazine product exposes real entry
        text.  Both the legacy ``magazine`` and the canonical
        ``magazine_digest`` product types are checked because the filename
        detection can resolve either spelling."""
        body = _render("magazine-digest.md.j2", _magazine_context())
        sections = _sections_from_headings(body, product_type)
        key_findings = sections.get("key_findings", "")
        assert key_findings
        assert "MagEntryTitleMarker" in key_findings


class TestEnterpriseNoOp:
    """#400: enterprise-briefing is flat H2 — level-aware parsing is a no-op."""

    def test_flat_h2_sections_are_unchanged(self) -> None:
        """#400: enterprise-briefing has no H3 children, so its canonical
        sections must be byte-identical before and after the fix — this is the
        false-failure guard for a flat template."""
        body = _render("enterprise-briefing.md.j2", _enterprise_context())
        sections = _sections_from_headings(body, "enterprise_briefing")
        assert sections.get("summary", "") == (
            "EntExecBody > **In this briefing**: 1 key points · drawn from 1 sources."
        )
        assert sections.get("key_findings", "") == "- EntFindingBody"
        assert sections.get("recommendations", "") == "- EntRecBody"


class TestPresentationNoOp:
    """#400: presentation slide fallback must be unaffected by nesting."""

    def test_slide_fallback_still_resolves(self) -> None:
        """#400: ``## Slide N:`` headings have no children, so the approach-B
        slide fallback must still populate ``key_findings`` with slide
        content — the level-aware change must not disturb it."""
        body = _render("presentation.md.j2", _presentation_context())
        sections = _sections_from_headings(body, "presentation")
        key_findings = sections.get("key_findings", "")
        assert "SlideBodyMarker" in key_findings
        assert "bul1" in key_findings


# ---------------------------------------------------------------------------
# Structural invariants: ordering + fences.
# ---------------------------------------------------------------------------


class TestOrderingTrap:
    """#400: a block must CLOSE before a sibling of equal-or-higher level."""

    def test_sibling_block_does_not_swallow_next_sibling(self) -> None:
        """#400: ``## Key Findings`` (with an H3 child) must stop at the next
        ``## Recommendations`` — a sibling must never swallow the next
        sibling's heading text or body.  This is the close-before-attribute
        rule that keeps section contents disjoint."""
        md = (
            "## Key Findings\n"
            "### NestedFinding\n"
            "NestedFindingBody\n"
            "## Recommendations\n"
            "RecommendationBody\n"
        )
        sections = _sections_from_headings(md, "report")
        key_findings = sections.get("key_findings", "")
        assert "NestedFindingBody" in key_findings
        assert "RecommendationBody" not in key_findings
        assert "recommendations" not in key_findings.lower()
        assert sections.get("recommendations", "") == "RecommendationBody"


class TestFenceAwareness:
    """#400: fenced code must not create headings or hijack canonical values."""

    def test_fenced_lines_are_not_headings(self) -> None:
        """#400: ``tutorial.md.j2`` wraps LLM code in a ```python fence.  A
        ``#`` comment line and a ``## Recommendations`` line inside that fence
        must NOT become headings — otherwise the enclosing ``## Content``
        truncates and ``recommendations`` is hijacked by the fenced text."""
        body = _render("tutorial.md.j2", _fenced_tutorial_context())
        sections = _sections_from_headings(body, "tutorial")
        summary = sections.get("summary", "")
        recommendations = sections.get("recommendations", "")
        assert "evil = 1" in summary
        assert "evil = 1" not in recommendations


class TestExercisePlaceholder:
    """#400: the B-04 empty-exercises placeholder must stay empty."""

    def test_no_exercises_placeholder_keeps_recommendations_empty(self) -> None:
        """#400: ``_No exercises provided._`` under ``## Exercises`` is
        genuinely empty content (B-04 stays rejected); absorbing children must
        not turn the placeholder into a non-empty ``recommendations`` value."""
        md = "## Content\n### Lesson\nLessonBody\n## Exercises\n_No exercises provided._\n"
        sections = _sections_from_headings(md, "tutorial")
        assert sections.get("recommendations", "") == ""
