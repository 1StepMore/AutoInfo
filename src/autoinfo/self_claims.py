"""Deterministic self-claim consistency for rendered products (issue #445).

Separate from :mod:`autoinfo.section_parser` on purpose: that module owns the
D1 "does the product carry its required sections" question, this one owns
"does the product describe itself correctly".  Both read a rendered body and
neither imports the other's state.

Two independent defects, two different severities, decided by measurement
over the 222 real product files under ``outputs/``:

1. **Count contradictions** — the product states a count of its own content
   that the rendered body does not carry ("2 selected items" over one Key
   Findings bullet; "60 source references listed" over eight References
   lines).  Every markdown template derives its own count from the very list
   it renders, so this is a zero-false-positive, fully-deterministic
   contradiction — it means the stated number and the rendered number came
   from DIFFERENT sources.  Action: hard block.

2. **Named items absent from the body** — the LLM narrative names an entity
   the rest of the product never mentions.  Measured on the same corpus this
   fires on ~27% of real products, almost entirely on legitimate summary
   prose ("the Smoky Mountains", "Southeast Asia", the synthesis's own
   finding labels).  A rule that wrong-accuses a quarter of shipped output
   cannot block delivery, so it escalates instead: it is flagged with its
   evidence and surfaces in ``DeliveryOutput.warnings`` and the per-product
   ``01-QA-GATES/gate-report-*.json``.  The hard-blocking answer to the
   fabrication class is upstream — the synthesis prompt constraint plus the
   deterministic synthesis grounding in :mod:`autoinfo.output`.
"""

from __future__ import annotations

import re

from autoinfo.section_parser import _SLIDE_HEADING_RE

# ---------------------------------------------------------------------------
# Self-claim consistency (issue #445)
# ---------------------------------------------------------------------------
#
# Two independent defects, two different severities, decided by measurement
# over the 222 real product files under ``outputs/``:
#
# 1. **Count contradictions** — the product states a count of its own content
#    that the rendered body does not carry ("2 selected items" over one Key
#    Findings bullet; "60 source references listed" over eight References
#    lines).  Every current markdown template already derives its own count
#    from the very list it renders, so this is a zero-false-positive,
#    fully-deterministic contradiction — it means the stated number and the
#    rendered number came from DIFFERENT sources.  Action: hard block.
#
# 2. **Named items absent from the body** — the LLM narrative names an entity
#    the rest of the product never mentions.  Measured on the same corpus this
#    fires on ~27% of real products, almost entirely on legitimate summary
#    prose ("the Smoky Mountains", "Southeast Asia", the synthesis's own
#    finding labels).  A rule that wrong-accuses a quarter of shipped output
#    cannot block delivery, so it escalates instead: it is flagged with its
#    evidence and surfaces in ``DeliveryOutput.warnings`` and the per-product
#    ``01-QA-GATES/gate-report-*.json``.  The hard-blocking answer to the
#    fabrication class is upstream — the synthesis prompt constraint plus the
#    deterministic synthesis grounding in ``autoinfo.output``.

#: Rendered-section heading aliases -> the item class that section carries.
_COUNTABLE_SECTIONS: dict[str, tuple[str, ...]] = {
    "key_findings": (
        "key findings",
        "key findings",
        "key_findings",
        "key-findings",
        "key takeaways",
        "key points",
        "main findings",
    ),
    "references": ("references", "sources", "source references"),
    "entries": ("entries", "items", "in this issue", "stories", "article index"),
    "slides": ("slide", "slides"),
}

#: Prose noun phrase -> the rendered item class it is a count OF, as candidate
#: classes in priority order (the first one the product actually renders
#: wins).  Kept deliberately tight: a loose vocabulary ("developments",
#: "stories covered", "highlights") turns narrative prose into a count claim
#: and re-introduces false positives.
_SELF_COUNT_NOUNS: dict[str, tuple[str, ...]] = {
    "key finding": ("key_findings",),
    "key findings": ("key_findings",),
    "key point": ("key_findings",),
    "key points": ("key_findings",),
    "key takeaway": ("key_findings",),
    "key takeaways": ("key_findings",),
    "main finding": ("key_findings",),
    "main findings": ("key_findings",),
    "source": ("references",),
    "sources": ("references",),
    "source link": ("references",),
    "source links": ("references",),
    "reference": ("references",),
    "references": ("references",),
    "entry": ("entries",),
    "entries": ("entries",),
    "article": ("entries", "key_findings"),
    "articles": ("entries", "key_findings"),
    "item": ("entries", "key_findings"),
    "items": ("entries", "key_findings"),
    "story": ("entries", "key_findings"),
    "stories": ("entries", "key_findings"),
    "slide": ("slides",),
    "slides": ("slides",),
}

_SELF_COUNT_RE = re.compile(
    r"(?<![\d.,])\b(?P<n>\d{1,4})\s+(?:of\s+\d{1,4}\s+)?"
    r"(?:selected\s+|key\s+|main\s+|source\s+|top\s+)*"
    r"(?P<noun>" + "|".join(sorted(_SELF_COUNT_NOUNS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

#: Narrative headings whose prose may assert a self-count.  The deterministic
#: scope lines the templates emit ("In this briefing: N key points") are
#: excluded from the SCAN but still participate in the COMPARISON — see
#: :func:`self_count_contradictions`.
_SELF_CLAIM_NARRATIVE_RE = re.compile(
    r"^#{1,6}\s*(?:the big idea|executive summary|summary|editor'?s note|the feature)\s*$",
    re.IGNORECASE,
)

_LIST_ITEM_RE = re.compile(r"^(?:[-*]\s+\S|\d+[.)]\s+\S|\[[ xX]\]\s+\S)")
_NUMBERED_HEADING_RE = re.compile(r"^#{1,6}\s+\d+[.)]\s+\S")


def _rendered_item_counts(lines: list[str]) -> dict[str, int]:
    """Count the items each countable section actually renders.

    Counts the *rendered* markup — list bullets, numbered list items, checkbox
    items, and numbered headings (premium-briefing's ``### 1. <takeaway>``) —
    inside each countable section's own block.  Nested content (a
    recommendations list inside a Key Findings block) is not counted: a
    heading closes its parent's block in the walker.  The ``slides`` class is
    heading-only — a slide's own bullets are slide content, not slides.
    """
    counts: dict[str, int] = {}
    index: dict[str, str] = {
        alias: key for key, aliases in _COUNTABLE_SECTIONS.items() for alias in aliases
    }
    open_key: str | None = None
    open_level = 0
    for line in lines:
        stripped = line.strip()
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", stripped)
        if heading:
            level = len(stripped) - len(stripped.lstrip("#"))
            normalized = heading.group(1).lower().replace("*", "").replace("`", "").strip()
            if open_key is not None and level <= open_level:
                open_key = None
            if _SLIDE_HEADING_RE.match(normalized):
                open_key = "slides"
            else:
                open_key = index.get(normalized)
            open_level = level if open_key else 0
            if open_key == "slides":
                counts["slides"] = counts.get("slides", 0) + 1
            elif open_key and _NUMBERED_HEADING_RE.match(stripped):
                counts[open_key] = counts.get(open_key, 0) + 1
            continue
        if open_key is None or open_key == "slides" or not _LIST_ITEM_RE.match(stripped):
            continue
        counts[open_key] = counts.get(open_key, 0) + 1
    return counts


def _self_claim_lines(lines: list[str]) -> list[str]:
    """Lines where a product may describe ITSELF: header, scope callout, narrative.

    Deliberately excludes entry tables, entry summaries and References — those
    carry third-party prose where ``1898 story`` is a fact about a book, not a
    claim about the product's size.
    """
    keep: list[str] = []
    seen_section = False
    for line in lines:
        if re.match(r"^#{1,6}\s", line.strip()):
            seen_section = True
        if line.strip().startswith(">") or not seen_section:
            keep.append(line)
    return keep + _narrative_prose(lines)


def _narrative_prose(lines: list[str]) -> list[str]:
    """Lines of the LLM-written narrative blocks (nested sub-sections excluded).

    ``digest.md.j2`` nests ``### Key Findings`` INSIDE its ``## Executive
    Summary``; those bullets are findings, not summary prose, so a deeper
    heading ends the narrative block instead of extending it.
    """
    kept: list[str] = []
    level = 0
    for line in lines:
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
        if heading:
            depth = len(line.strip()) - len(line.strip().lstrip("#"))
            if _SELF_CLAIM_NARRATIVE_RE.match(line.strip()):
                level = depth
            elif level and depth <= level:
                level = 0
            continue
        if level:
            kept.append(line)
    return kept


def self_count_contradictions(text: str) -> list[str]:
    """Defect strings for self-count claims the rendered body does not carry.

    A product may state how much content it contains — ``3 key points drawn
    from 25 sources``, ``**Slides**: 6``.  Each stated number is compared
    against the number of items the SAME product renders for that class; a
    mismatch means the two numbers came from different sources (#445
    "Executive Summary contradicts the body").  In the ``selected N of M
    items`` scope line only N is a self-count; M is the pool it drew from.

    Sections the product does not render are NOT a contradiction — a column
    has no Key Findings section, so a narrative mention of key findings has
    nothing to contradict.  Only rendered classes are compared, which is what
    keeps this rule free of false positives.
    """
    lines = text.splitlines()
    rendered = _rendered_item_counts(lines)
    if not rendered:
        return []
    defects: list[str] = []
    for line in _self_claim_lines(lines):
        for match in _SELF_COUNT_RE.finditer(line):
            item_class = next(
                (c for c in _SELF_COUNT_NOUNS[match.group("noun").lower()] if c in rendered),
                None,
            )
            if item_class is None:
                continue
            claimed = int(match.group("n"))
            if claimed != rendered[item_class]:
                defect = (
                    f"self-count claim {match.group(0)!r} contradicts the "
                    f"{rendered[item_class]} rendered {item_class.replace('_', ' ')}"
                )
                if defect not in defects:
                    defects.append(defect)
    return defects


def self_claim_orphan_entities(text: str) -> list[str]:
    """Entity names the LLM narrative introduces that the body never states.

    The escalation half of :func:`self_count_contradictions`.  Returns human
    readable defect strings; the caller flags rather than blocks (see the
    calibration note above).  Honest hedges are exempt — a product that says a
    detail "is not disclosed in the available sources" is CORRECT behaviour
    (#179/#191).
    """
    from autoinfo.grounding import ungrounded_entities  # noqa: PLC0415

    lines = text.splitlines()
    narrative = "\n".join(_narrative_prose(lines))
    if len(narrative.strip()) < 60:
        return []
    corpus = "\n".join(line for line in lines if line not in _narrative_prose(lines))
    return [
        f"narrative names {entity!r}, which the rest of the product never states"
        for entity in ungrounded_entities(narrative, corpus)
    ]
