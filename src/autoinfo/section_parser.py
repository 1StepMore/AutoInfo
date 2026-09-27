"""Canonical D1 section parser — the single source of truth (#400).

Historically this parser existed as three separate copies:

- ``autoinfo.output``
- ``autoinfo.delivery.gate_report``
- ``scripts/validation_delivery.py``

The copies drifted. Issue #396 added the ``"key takeaways"`` /
``"recommended actions"`` heading aliases to two of the three copies and
silently left ``scripts/validation_delivery.py`` on the stale pre-#396 table,
so the validation-packaging path never received the fix. This module removes
the duplication: all three sites re-export the SAME objects from here, so a
change can never again reach only some copies.

The module is deliberately pure and top-level: it imports only ``re`` and
stdlib typing. Importing a submodule executes the parent package ``__init__``,
and both ``autoinfo.output`` and ``autoinfo.delivery`` are heavy (template
registries, LLM config, delivery channels); a neutral top-level module avoids
those import side effects and any import cycle while all three consumers can
import it.

Behaviour owned by this module (issue #400):

- ``_is_empty_placeholder`` is the skeleton-aware variant: a body that is only
  an empty-state placeholder (``_No exercises provided._``) or only an echoed
  LLM prompt skeleton (``<finding 1>``) counts as empty. The historical
  ``gate_report`` / ``validation_delivery`` copies did not know the skeleton
  form, so unifying on this version intentionally TIGHTENS those packaging
  paths — a skeleton-only body is now treated as empty instead of passing.
- ``_PRODUCT_TYPE_REQUIRED_SECTIONS`` is keyed by underscore spellings while
  the generation path passes hyphen family names (``premium-briefing``), so
  every entry point normalizes the product type first; without that the lookup
  misses, falls back to the ``report`` rules (all three sections required) and
  D1-blocks a complete premium/enterprise briefing.
- ``magazine_digest`` emits no summary-alias heading, so the any-content
  fallback also serves ``magazine_digest`` and yields ``key_findings``.
"""

from __future__ import annotations

import re

# Canonical D1 sections -> markdown heading aliases (#172, #396).
_SECTION_HEADING_ALIASES: dict[str, tuple[str, ...]] = {
    "key_findings": (
        "key findings",
        "key_findings",
        "key-findings",
        "key points",
        "slide",
        "slides",
        "learning objectives",
        "main findings",
        "introduction",
        "key takeaways",
    ),
    "summary": (
        "summary",
        "executive summary",
        "overview",
        "entries",
        "content",
        "executive overview",
        "body",
    ),
    "recommendations": (
        "recommendations",
        "conclusion",
        "next steps",
        "exercises",
        "further reading",
        "action items",
        "next actions",
        "recommended actions",
    ),
}

# Presentation slide headings: "Slide N: ..." -> key_findings (#172).
_SLIDE_HEADING_RE = re.compile(r"^slide\s*\d+\s*:", re.IGNORECASE)

# Digest entry headings: "1. Title" / "1) Title" -> entries present (#172).
_ENTRY_HEADING_RE = re.compile(r"^\d+[.)]\s+\S", re.IGNORECASE)

# Empty-state placeholder content templates emit when no content was produced
# (e.g. "_No objectives defined._", "_No exercises provided._"). It is
# genuinely empty content, not a real section — B-04 must stay rejected (#172).
_EMPTY_PLACEHOLDER_RE = re.compile(r"^\s*_no\s+.+_\.?\s*$", re.IGNORECASE)

# LLM skeleton echo: a body that is only prompt-template placeholders such as
# "<finding 1>" or "- <finding 1> - <finding 2>". Also genuinely empty (#400).
_LLM_SKELETON_RE = re.compile(
    r"^\s*[-*|]?\s*<[a-z0-9 _\-]+>"
    r"(\s*[-*|]\s*<[a-z0-9 _\-]+>)*\s*$",
    re.IGNORECASE,
)

# Canonical D1 sections each product type must genuinely contain. Sections
# outside a type's required set are still checked by the D1 gate (it always
# requires all three); they get a non-empty marker so a complete product of
# that format is not false-rejected (#172). Keys are the normalized
# (underscore) spellings — see :func:`_normalize_product_type`.
_PRODUCT_TYPE_REQUIRED_SECTIONS: dict[str, tuple[str, ...]] = {
    "report": ("key_findings", "summary", "recommendations"),
    "presentation": ("key_findings",),
    "digest": ("summary",),
    "tutorial": ("key_findings", "recommendations"),
    "column": ("key_findings",),
    "magazine": ("key_findings",),
    "enterprise_briefing": ("summary",),
    "premium_briefing": ("summary",),
    # magazine-digest.md.j2 emits no summary-alias heading; its content is
    # rescued into key_findings by the any-content fallback (#400).
    "magazine_digest": ("key_findings",),
}

# Non-empty marker for canonical sections a product format does not produce
# but the D1 gate always checks. Only applied to sections OUTSIDE the product
# type's required set, so genuinely empty products still fail (#172).
_D1_NON_REQUIRED_MARKER = "present"


def _normalize_product_type(product_type: str) -> str:
    """Normalize a product-type spelling to the canonical underscore form.

    ``_PRODUCT_TYPE_REQUIRED_SECTIONS`` is keyed by underscore names
    (``premium_briefing``), but the generation path passes the registry family
    name with a hyphen (``premium-briefing``). Without normalization the
    lookup misses and falls back to the ``report`` rules (all three sections
    required), which D1-blocks a complete premium briefing (#400 finding F9).
    Idempotent: ``strip`` / ``lower`` / ``-`` -> ``_``.
    """
    return product_type.strip().lower().replace("-", "_")


def _is_empty_placeholder(content: str) -> bool:
    """True when *content* is an empty-state placeholder or LLM skeleton echo."""
    stripped = content.strip()
    if not stripped:
        return False
    return bool(_EMPTY_PLACEHOLDER_RE.match(stripped) or _LLM_SKELETON_RE.match(stripped))


def _sections_from_headings(text: str, product_type: str = "report") -> dict[str, str]:
    """Map canonical D1 sections to non-empty heading content (md/html).

    Headings are matched against :data:`_SECTION_HEADING_ALIASES`, with
    format-specific additions per *product_type* (approach A + B, #172):

    - ``Slide N:`` headings (presentation) -> ``key_findings``
    - numbered entry headings (digest) count as an ``summary``/Entries
    - column/magazine/magazine_digest products pass when any content heading
      is non-empty

    Empty-state placeholder content (``_No objectives defined._``) is treated
    as empty so a genuinely empty product still fails D1.
    """
    product_type = _normalize_product_type(product_type)
    found: dict[str, str] = {}
    heading_re = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
    if heading_re.search(text):
        converted: list[str] = []
        pos = 0
        for m in heading_re.finditer(text):
            converted.append(text[pos : m.start()])
            converted.append(
                "\n"
                + "#" * int(m.group(1))
                + " "
                + re.sub(r"<[^>]+>", "", m.group(2)).strip()
                + "\n"
            )
            pos = m.end()
        converted.append(text[pos:])
        text = re.sub(r"<[^>]+>", " ", "".join(converted))
    blocks: list[tuple[str, list[str]]] = []
    cur_heading: str | None = None
    cur_lines: list[str] = []
    for line in text.splitlines():
        hm = re.match(r"^#{1,6}\s+(.+?)\s*$", line.strip())
        if hm:
            if cur_heading:
                blocks.append((cur_heading, cur_lines))
            cur_heading = hm.group(1).lower().replace("*", "").replace("`", "").strip()
            cur_lines = []
        elif cur_heading:
            cur_lines.append(line.strip())
    if cur_heading:
        blocks.append((cur_heading, cur_lines))

    def _block_content(heading: str, lines: list[str]) -> str:
        body_lines = [line for line in lines if line and not re.match(r"^[-*=_]{3,}\s*$", line)]
        content = " ".join(body_lines)
        if _is_empty_placeholder(content):
            return ""
        return content

    for canonical, aliases in _SECTION_HEADING_ALIASES.items():
        for heading, lines in blocks:
            if heading in aliases and canonical not in found:
                content = _block_content(heading, lines)
                if content or _is_empty_placeholder(
                    " ".join(
                        line for line in lines if line and not re.match(r"^[-*=_]{3,}\s*$", line)
                    )
                ):
                    found[canonical] = content or ""
    if "key_findings" not in found:
        slide_parts: list[str] = []
        for heading, lines in blocks:
            if _SLIDE_HEADING_RE.match(heading):
                content = _block_content(heading, lines)
                if content:
                    slide_parts.append(content)
        if slide_parts:
            found["key_findings"] = " ".join(slide_parts)
    if "summary" not in found:
        entry_count = 0
        for heading, lines in blocks:
            if _ENTRY_HEADING_RE.match(heading):
                content = _block_content(heading, lines)
                if content:
                    entry_count += 1
        if entry_count:
            found["summary"] = "present"
    # Approach B: column/magazine/magazine_digest pass with any content
    # heading. The guard keys on ``key_findings`` (which this fallback exists
    # to supply), not on the whole ``found`` dict: an already-found summary
    # must not suppress the required key_findings fallback (#400).
    if product_type in ("column", "magazine", "magazine_digest") and "key_findings" not in found:
        for heading, lines in blocks:
            content = _block_content(heading, lines)
            if content:
                found["key_findings"] = content
                break
    return found


def _apply_format_sections(sections: dict[str, str], product_type: str) -> dict[str, str]:
    """Map a product's detected sections onto the three D1 canonical keys.

    The D1 gate always requires ``key_findings``/``summary``/``recommendations``
    to be present and non-empty, but each product format only genuinely
    produces a subset (report: all three; presentation: slides; digest:
    entries; tutorial: objectives + exercises). Sections outside the type's
    required set get a non-empty marker so a complete product of that format
    is not false-rejected; sections inside the set keep their detected value
    (empty stays empty -> D1 still blocks genuinely empty products, #172).
    """
    product_type = _normalize_product_type(product_type)
    required = _PRODUCT_TYPE_REQUIRED_SECTIONS.get(
        product_type, _PRODUCT_TYPE_REQUIRED_SECTIONS["report"]
    )
    mapped: dict[str, str] = {}
    for canonical in ("key_findings", "summary", "recommendations"):
        value = sections.get(canonical, "")
        if canonical not in required and not value:
            value = _D1_NON_REQUIRED_MARKER
        mapped[canonical] = value
    return mapped
