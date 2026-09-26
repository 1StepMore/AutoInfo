"""#396: premium/enterprise briefing headings must map to D1 gate sections.

``premium-briefing.md.j2`` renders ``## Key Takeaways`` and
``## Recommended Actions``, but ``_SECTION_HEADING_ALIASES`` only knew the
report-family spellings (``key findings`` / ``recommendations``). A premium
product therefore parsed with ``summary`` alone: ``key_findings`` and
``recommendations`` came back *absent* even though the body carried real
content, so D1 saw a structurally empty product.

The alias table is duplicated in two modules (``autoinfo.delivery.gate_report``
and ``autoinfo.output``) so both the gate path and the D1 product-quality path
resolve premium headings. The duplication is real but was previously harmless
because the two tables happened to be identical — a silent-drift hazard. The
parity test below locks them together, so the fix cannot be applied to one
table and forgotten in the other.

All tests are hermetic: pure string parsing, no files, no LLM, no network.
"""

from __future__ import annotations

import pytest

from autoinfo.delivery import gate_report as gr
from autoinfo.output import _SECTION_HEADING_ALIASES as OUTPUT_ALIASES
from autoinfo.output import _sections_from_headings as output_sections_from_headings

#: A minimal premium product carrying real content under the template's
#: actual headings. Before the fix only ``summary`` was detected.
PREMIUM_BRIEFING_MD = """# Premium Briefing

## Executive Summary
Market shifted this week.

## Key Takeaways
1. Hospitals adopt AI triage at growing scale
2. Reimbursement codes remain the main blocker

## Risks & Opportunities
- Regulatory drift in two states

## Recommended Actions
- Audit vendor contracts before renewal

## References
- https://example.org/a
"""


class TestAliasTableParity:
    """The two duplicated alias tables must never drift apart."""

    def test_tables_are_identical(self) -> None:
        assert gr._SECTION_HEADING_ALIASES == OUTPUT_ALIASES, (
            "gate_report and output alias tables have drifted; a heading added "
            "to one must be added to the other (#396)"
        )

    def test_premium_headings_present_in_both_tables(self) -> None:
        for table, name in (
            (gr._SECTION_HEADING_ALIASES, "gate_report"),
            (OUTPUT_ALIASES, "output"),
        ):
            assert "key takeaways" in table["key_findings"], name
            assert "recommended actions" in table["recommendations"], name


class TestPremiumHeadingsParse:
    """Premium headings must resolve in BOTH consumers of the alias table."""

    @pytest.mark.parametrize(
        ("parser", "label"),
        [
            (gr._sections_from_headings, "gate_report"),
            (output_sections_from_headings, "output"),
        ],
    )
    def test_all_three_sections_detected(self, parser, label: str) -> None:
        sections = parser(PREMIUM_BRIEFING_MD, "report")

        assert sections["summary"] == "Market shifted this week.", label
        assert "Hospitals adopt AI triage" in sections["key_findings"], label
        assert "Audit vendor contracts" in sections["recommendations"], label

    def test_key_takeaways_still_mapped_for_report_product_type(self) -> None:
        """The alias applies regardless of the product_type argument."""
        for product_type in ("report", "premium-briefing", "enterprise-briefing"):
            sections = gr._sections_from_headings(PREMIUM_BRIEFING_MD, product_type)
            assert sections["key_findings"], product_type
            assert sections["recommendations"], product_type

    def test_existing_report_headings_still_work(self) -> None:
        """Adding premium aliases must not regress the report-family spellings."""
        report_md = (
            "# Weekly Report\n\n"
            "## Executive Summary\nSummary body.\n\n"
            "## Key Findings\nFinding body.\n\n"
            "## Recommendations\nRecommendation body.\n"
        )
        sections = gr._sections_from_headings(report_md, "report")
        assert sections["summary"] == "Summary body."
        assert sections["key_findings"] == "Finding body."
        assert sections["recommendations"] == "Recommendation body."
