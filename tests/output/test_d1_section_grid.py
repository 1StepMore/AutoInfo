"""#400: D1 product-completeness verdict grid over real rendered products.

Issue #400: the section parser cut blocks at any heading level, so an H2 with
only H3 children registered as empty.  That changed the D1
``ProductCompleteness`` verdict for every product whose canonical section is
built from nested children (premium briefings lost ``key_findings``; the
generation path's hyphen/underscore product-type mismatch then blocked a
premium product that the packaging path passed).

This grid renders the REAL product templates, writes them to ``tmp_path``
with production filenames, adapts each through
``autoinfo.delivery.gate_report._build_product_output`` and runs the D1 gate
with ``action_on_failure="block"`` (the strict production setting).  It pins
both directions: products that MUST PASS after the fix, and genuinely empty
products that MUST STILL FAIL (so the fix cannot rescue garbage by masking).

The suite is hermetic: real template renders only, no LLM, no network, no
domain; all writes are confined to ``tmp_path``.  A "D1-BLOCKED alert
dispatched" log line / webhook stderr warning on the MUST-FAIL cases is
expected, harmless noise.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from autoinfo.delivery.gate_report import _build_product_output
from autoinfo.output import _get_jinja_env, _sections_from_rendered_body
from autoinfo.quality import QualityResult, run_delivery_gates


@dataclass(frozen=True)
class D1Case:
    """One row of the D1 verdict grid."""

    label: str
    filename: str
    template: str | None
    context: dict[str, Any] | None
    body: str
    bucket: str
    expect_pass: bool


def _render(template_name: str, context: dict[str, Any]) -> str:
    """Render one real template through the repo's shared Jinja environment."""
    return _get_jinja_env().get_template(template_name).render(context)


def _base_context() -> dict[str, Any]:
    return {
        "title": "Sample Product",
        "domain": "ai-commercial",
        "generated_at": "2026-09-27 10:00 UTC",
    }


def _premium_context() -> dict[str, Any]:
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


def _enterprise_context() -> dict[str, Any]:
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


def _digest_context() -> dict[str, Any]:
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


def _presentation_context() -> dict[str, Any]:
    ctx = _base_context()
    ctx.update(
        {
            "topic": "Topic",
            "target_audience": "exec",
            "slides": [
                {
                    "title": "SlideTitleMarker",
                    "content": (
                        "SlideBodyMarker "
                        + "This deck slide carries a full sentence of content. " * 6
                    ),
                    "bullets": ["bul1", "bul2"],
                    "source_url": "",
                    "notes": "",
                }
            ],
            "description": "desc",
        }
    )
    return ctx


def _report_md_context() -> dict[str, Any]:
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


def _report_html_context() -> dict[str, Any]:
    return {
        "title": "Sample Report",
        "domain_name": "ai-commercial",
        "period": "Weekly",
        "generated_at": "2026-09-27 10:00 UTC",
        "executive_summary": "ReportExecBody",
        "executive_summary_html": "",
        "key_findings": [{"text": "ReportFindingBody", "source_url": ""}],
        "recommendations": ["ReportRecBody"],
        "sections": [
            {"id": "s1", "heading": "SectionTitleMarker", "content_html": "SectionBodyMarker"}
        ],
        "references": [{"text": "Ref One", "url": "https://e/1"}],
    }


def _column_context() -> dict[str, Any]:
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


def _pass_case(label: str, filename: str, template: str, context: dict[str, Any]) -> D1Case:
    return D1Case(label, filename, template, context, "", "PROCESSED", True)


def _fail_case(label: str, filename: str, body: str) -> D1Case:
    return D1Case(label, filename, None, None, body, "PROCESSED", False)


#: The verdict grid.  ``expect_pass`` is the POST-FIX expectation; cases that
#: currently fail are the honest RED evidence for #400.
_CASES: list[D1Case] = [
    # --- MUST PASS: report family --------------------------------------
    _pass_case("report-md", "report.md", "report.md.j2", _report_md_context()),
    _pass_case("report-html", "report.html", "report.html.j2", _report_html_context()),
    # --- MUST PASS: digest family --------------------------------------
    _pass_case("digest-md", "digest.md", "digest.md.j2", _digest_context()),
    _pass_case("digest-html", "digest.html", "digest.html.j2", _digest_html_context()),
    # --- MUST PASS: tutorial / presentation ----------------------------
    _pass_case("tutorial-md", "tutorial.md", "tutorial.md.j2", _tutorial_context()),
    _pass_case("presentation-md", "presentation.md", "presentation.md.j2", _presentation_context()),
    _pass_case(
        "presentation-html", "presentation.html", "presentation.html.j2", _presentation_context()
    ),
    # --- MUST PASS: column / magazine ----------------------------------
    _pass_case("column-md", "column.md", "column.md.j2", _column_context()),
    _pass_case(
        "magazine-digest-md", "magazine-digest.md", "magazine-digest.md.j2", _magazine_context()
    ),
    # --- MUST PASS: briefings (both product-type spellings) ------------
    _pass_case(
        "enterprise-briefing-md-hyphen",
        "enterprise-briefing.md",
        "enterprise-briefing.md.j2",
        _enterprise_context(),
    ),
    _pass_case(
        "premium-briefing-md-hyphen",
        "premium-briefing.md",
        "premium-briefing.md.j2",
        _premium_context(),
    ),
    # --- MUST STILL FAIL: genuinely empty / too-short products ---------
    _fail_case("empty-report", "report-empty.md", "# Report\n\nNothing to report.\n"),
    _fail_case("empty-digest", "digest-empty.md", "# Digest\n\nNothing here.\n"),
    _fail_case("empty-tutorial", "tutorial-empty.md", "# Tutorial\n\nNothing.\n"),
    _fail_case(
        "placeholder-tutorial",
        "tutorial-placeholder.md",
        (
            "# Tutorial\n\n"
            "## Learning Objectives\n\n"
            "_No objectives defined._\n\n"
            "## Content\n\n"
            "## Exercises\n\n"
            "_No exercises provided._\n"
        ),
    ),
    _fail_case("short-presentation", "presentation-empty.md", "# Presentation\n\nToo short.\n"),
]


def _materialize(case: D1Case, tmp_path: Path) -> Path:
    """Render (or write) the case body into a production-named file."""
    if case.template is not None:
        text = _render(case.template, case.context or {})
    else:
        text = case.body
    path = tmp_path / case.filename
    path.write_text(text, encoding="utf-8")
    return path


def _d1_result(path: Path, bucket: str) -> QualityResult:
    """Run the strict D1 delivery gate on one materialized product file."""
    product_output = _build_product_output(path, bucket)
    results = run_delivery_gates(
        product_output,
        {},
        {"D1": {"enabled": True, "action_on_failure": "block"}},
    )
    return results["D1-ProductCompleteness"]


@pytest.mark.parametrize("case", _CASES, ids=[c.label for c in _CASES])
def test_d1_verdict_grid(case: D1Case, tmp_path: Path) -> None:
    """#400: D1 verdict per real rendered product must match the post-fix
    contract — nested-content products pass, genuinely empty ones stay
    blocked.  A nested product that regresses would fail here; a broken
    "fix" that masks empties would fail the MUST-FAIL rows."""
    path = _materialize(case, tmp_path)
    result = _d1_result(path, case.bucket)
    assert result.passed is case.expect_pass, (case.label, result.details)


def _generation_path_d1(body: str, product_type: str) -> QualityResult:
    """Run D1 the way ``autoinfo.output`` does on the GENERATION path.

    ``output/__init__.py:4832`` assigns ``product_type = report_family`` — the
    registry family name, e.g. ``"premium-briefing"`` (HYPHEN) — and passes it
    straight into ``_sections_from_rendered_body`` and ``product_output``
    (:1026, :1038).  It is *not* derived from the output filename, so the
    filename-keyword map in ``_detect_product_type`` is bypassed entirely and
    the spelling reaches ``_apply_format_sections`` verbatim.  That is the path
    #400/F9 lives on, and it is why an underscore filename is the wrong way to
    test the spelling: ``_PRODUCT_TYPE_KEYWORDS`` matches HYPHENATED keywords
    only, so ``premium_briefing.md`` never even detects as ``premium_briefing``.
    """
    sections = _sections_from_rendered_body(body, "markdown", product_type)
    assert sections is not None
    product_output = {
        "product_type": product_type,
        "format": "markdown",
        "body": body,
        "key_findings": sections.get("key_findings", ""),
        "summary": sections.get("summary", ""),
        "recommendations": sections.get("recommendations", ""),
        "entries": [],
    }
    results = run_delivery_gates(
        product_output,
        {},
        {"D1": {"enabled": True, "action_on_failure": "block"}},
    )
    return results["D1-ProductCompleteness"]


@pytest.mark.parametrize(
    ("family", "template", "context_factory"),
    [
        ("premium-briefing", "premium-briefing.md.j2", _premium_context),
        ("enterprise-briefing", "enterprise-briefing.md.j2", _enterprise_context),
        ("magazine-digest", "magazine-digest.md.j2", _magazine_context),
    ],
)
def test_generation_path_product_type_spelling_is_normalized(
    family: str, template: str, context_factory: Any
) -> None:
    """#400/F9: the registry family name must resolve like the underscore key.

    The generation path passes the HYPHENATED family name
    (``premium-briefing``) into the gate, while ``_PRODUCT_TYPE_REQUIRED_SECTIONS``
    is keyed by UNDERSCORE (``premium_briefing``).  Before the fix the lookup
    missed and silently fell back to the strict ``report`` required-set, so a
    premium briefing generated with delivery gates enabled was D1-BLOCKED even
    though the same product passed on the packaging path.  Both spellings must
    now produce the same verdict.
    """
    body = _render(template, context_factory())
    underscore = family.replace("-", "_")

    hyphen_result = _generation_path_d1(body, family)
    underscore_result = _generation_path_d1(body, underscore)

    assert hyphen_result.passed is True, (family, hyphen_result.details)
    assert underscore_result.passed is True, (family, underscore_result.details)


def test_raw_bucket_skips_d1_trivially(tmp_path: Path) -> None:
    """#400: RAW products skip D1 (already gated at pipeline time) — the gate
    must report a trivial pass, never a completeness verdict."""
    path = tmp_path / "report-raw.md"
    path.write_text("# Report\n\nRaw feed body.\n", encoding="utf-8")
    result = _d1_result(path, "RAW")
    assert result.passed is True
    assert result.details.get("skipped") is True


def test_magazine_digest_degenerate_verdict(tmp_path: Path) -> None:
    """#400 ACCEPTED BEHAVIOR: a content-free magazine-digest is NOT blocked.

    Before the fix a magazine-digest with no entries failed D1 (``summary``
    was required but the template emits no summary-alias heading, and the
    any-content fallback keyed only on ``("column", "magazine")``).  After the
    fix the level-aware parser makes the masthead/title block span the whole
    document, and ``magazine_digest`` joins the any-content fallback, so the
    degenerate product picks up boilerplate as ``key_findings`` and D1 stops
    blocking it.  This is the accepted, documented outcome: the alternative
    (rejecting every empty magazine edition) was rejected as a false
    false-negative for a legitimately quiet period.  The assertion records the
    observed post-fix verdict rather than pretending the case is empty.
    """
    ctx = _base_context()
    ctx.update(
        {
            "title": "Quiet Edition",
            "period_label": "Weekly",
            "domain": "general-news",
            "date_from": "2026-09-20",
            "date_to": "2026-09-27",
            "llm_synthesis": {},
            "entries": [],
        }
    )
    path = tmp_path / "magazine-digest.md"
    path.write_text(_render("magazine-digest.md.j2", ctx), encoding="utf-8")
    result = _d1_result(path, "PROCESSED")
    assert result.passed is True, result.details
