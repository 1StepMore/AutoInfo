"""Report/digest audience vocabulary (extracted from output/__init__.py)."""

from __future__ import annotations


def _normalize_report_audience(target_audience: str) -> str:
    """Validate and normalize target_audience for report/digest generation.

    Returns the audience key if valid.  An empty or ``None``-like string
    resolves to ``"general"`` (no error).  A non-empty invalid audience
    raises :class:`ValueError` with a message naming the invalid value
    and listing valid options — mirroring tutorial/presentation behavior
    (issue #297).
    """
    if not target_audience:
        return "general"
    audience = target_audience.strip().lower()
    if audience in _VALID_REPORT_AUDIENCES:
        return audience
    raise ValueError(
        f"Invalid target_audience '{target_audience}'. "
        f"Must be one of: {', '.join(sorted(_VALID_REPORT_AUDIENCES))}"
    )


_REPORT_AUDIENCE_PROMPTS: dict[str, str] = {
    "researcher": (
        "Structure the summary with: Methods & Data Sources, Key Results, "
        "Limitations, Discussion. Use technical terminology and cite "
        "specific findings where possible."
    ),
    "executive": (
        "Structure the summary with: Key Findings, Strategic Implications, "
        "Recommended Actions. Keep language concise and actionable."
    ),
    "investor": (
        "Structure the summary with: Market Context, Opportunities & Risks, "
        "Competitive Position. Focus on growth potential and ROI."
    ),
    "clinician": (
        "Structure the summary with: Practical Applications, Clinical "
        "Guidelines, Patient Outcomes. Emphasize actionable takeaways."
    ),
    "student": (
        "Structure the summary with: Foundational Concepts, Step-by-Step "
        "Explanations, Key Definitions, Study Takeaways. Use accessible language."
    ),
    "general": "",  # no special structure — existing behavior
}


_VALID_REPORT_AUDIENCES: list[str] = list(_REPORT_AUDIENCE_PROMPTS.keys())


_REPORT_AUDIENCE_DESCRIPTIONS: dict[str, str] = {
    "researcher": "technical depth, citations, methodology focus, statistical rigor",
    "executive": "strategic overview, ROI, competitive landscape, high-level implications",
    "investor": "market context, opportunities & risks, competitive position, growth potential",
    "clinician": "practical application, clinical guidelines, patient outcomes, treatment protocols",  # noqa: E501
    "student": "foundational concepts, simplified explanations, step-by-step learning, study aids",
    "general": "balanced overview suitable for any audience — no special structure applied",
}


_VALID_AUDIENCES = frozenset(_VALID_REPORT_AUDIENCES)


_AUDIENCE_DESCRIPTIONS: dict[str, str] = dict(_REPORT_AUDIENCE_DESCRIPTIONS)
