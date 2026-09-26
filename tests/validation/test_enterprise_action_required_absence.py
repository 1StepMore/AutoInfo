"""#397: an OMITTED ``Action Required`` section is not a defect.

``_so_what_substantive`` required ``- [ ]`` checkboxes inside the
``## Action Required`` section unconditionally. But #380/#391 established the
product rule that a section with no content is **omitted entirely** rather
than shipped as a hollow heading or a ``_No ..._`` filler. So a correctly
rendered enterprise briefing with no action items omitted the section, and the
gate then failed it P1 with "Action Required has no - [ ] item" — a false
positive contradicting the product's own rendering rule.

``_section_text`` returns ``""`` for an absent section and ``"\n"`` for a
present-but-empty one, so a truthiness guard separates the two cases:

- heading absent (correct rendering)  -> not weak
- heading present but empty (defect)  -> still weak P1

The ``Recommendations`` guard already used this idiom; ``Action Required`` was
the outlier. These tests pin BOTH cases, because a fix that simply dropped the
check would pass the false-positive case and silently stop catching the real
defect.

Hermetic: pure string parsing, no LLM, no network.
"""

from __future__ import annotations

from autoinfo.validation_matrix import _so_what_substantive

#: Correct rendering: no action items, so the section is omitted entirely.
_ACTION_SECTION_OMITTED = """# Enterprise Briefing

## Executive Summary
Sector quiet this week.

## Recommendations
- Keep monitoring the vendor landscape
"""

#: Defect: the heading is rendered but carries no checkbox.
_ACTION_SECTION_PRESENT_BUT_EMPTY = """# Enterprise Briefing

## Executive Summary
Sector quiet this week.

## Action Required

## Recommendations
"""

#: Healthy: the section is present and carries checkboxes.
_ACTION_SECTION_POPULATED = """# Enterprise Briefing

## Executive Summary
Sector quiet this week.

## Action Required
- [ ] Audit vendor contracts
- [ ] Renew the regional licence

## Recommendations
- Keep monitoring the vendor landscape
"""

_RESULT = "ai-commercial"
_PRODUCT = "enterprise-briefing"


class TestActionRequiredOmission:
    """The false positive: a correctly omitted section must PASS."""

    def test_omitted_action_section_does_not_fail(self) -> None:
        result = _so_what_substantive(_ACTION_SECTION_OMITTED, _RESULT, _PRODUCT)

        assert result.passed is True, f"false P1 on an omitted section: {result.details}"
        assert "Action Required" not in result.details

    def test_omitted_action_section_keeps_other_findings(self) -> None:
        """Omission must not mask a genuine defect elsewhere in the product."""
        broken_recs = (
            "# Enterprise Briefing\n\n"
            "## Executive Summary\nSector quiet this week.\n\n"
            "## Recommendations\n"
        )
        result = _so_what_substantive(broken_recs, _RESULT, _PRODUCT)

        assert result.passed is False
        assert "Recommendations empty" in result.details
        assert "Action Required" not in result.details


class TestActionRequiredPresentButEmpty:
    """The real defect: a rendered but empty section must still FAIL."""

    def test_present_empty_action_section_fails_p1(self) -> None:
        result = _so_what_substantive(_ACTION_SECTION_PRESENT_BUT_EMPTY, _RESULT, _PRODUCT)

        assert result.passed is False, "a hollow rendered section must not pass"
        assert result.severity == "P1"
        assert "Action Required has no - [ ] item" in result.details

    def test_present_empty_is_distinguished_from_omitted(self) -> None:
        """The two cases must not collapse to the same verdict (#397)."""
        omitted = _so_what_substantive(_ACTION_SECTION_OMITTED, _RESULT, _PRODUCT)
        hollow = _so_what_substantive(_ACTION_SECTION_PRESENT_BUT_EMPTY, _RESULT, _PRODUCT)

        assert omitted.passed is True
        assert hollow.passed is False


class TestActionRequiredPopulated:
    def test_populated_action_section_passes(self) -> None:
        result = _so_what_substantive(_ACTION_SECTION_POPULATED, _RESULT, _PRODUCT)
        assert result.passed is True, result.details
