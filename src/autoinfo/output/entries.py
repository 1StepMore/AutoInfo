"""Shared deterministic entry-filter kernel (extracted from :mod:`autoinfo.output`, T10).

Pure relocation of the entry-filter block out of the 13K-line package
``__init__``: display-name mapping, test/empty-entry guards, near-duplicate
convergence, language filters, and the per-domain exclude-keyword /
relevance-floor admission filters.  Every moved name is re-exported from
:mod:`autoinfo.output` (see the shim there), so no caller changes.

Import direction
----------------
This module is imported *by* :mod:`autoinfo.output`; importing the package back
at module scope would cycle.  Names that must stay resolvable through the
package namespace (either because they live in ``__init__`` or because the
module-boundary tests patch ``autoinfo.output.<name>``) are therefore imported
function-locally:

* ``get_config_path`` / ``load_config`` / ``_DEMO_DOMAINS_DIR`` /
  ``datetime`` -- package seams the characterization tests patch on
  ``autoinfo.output`` (``tests/output/test_entry_filters_boundary.py``,
  ``tests/output/test_language_filter.py``, ``tests/output/test_digest.py``).
* ``_is_lang_learning_domain`` -- helper that stays in ``__init__`` (the
  pre-existing lazy import is preserved verbatim).

Everything else (``autoinfo.textutil`` event-signature helpers, stdlib, yaml)
stays a direct import exactly as before.
"""

from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Final

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Language-teaching topic guard (backup #63)
# ---------------------------------------------------------------------------
# A language-learning domain's entries must not include content that teaches
# a language OTHER than the domain's ``default_language`` — e.g. a Spanish
# grammar post on blog.duolingo.com leaking into english-learning (the list
# is about the topic, so the language filter cannot catch it).  This is a
# deterministic title/summary heuristic that drops entries whose text
# combines a non-target language name with a language-teaching signal.

_LANG_TEACHING_SIGNALS: tuple[str, ...] = (
    " mean ",
    "means",
    "meaning",
    "grammar",
    "vocabulary",
    "conjugation",
    "pronunciation",
    "how to say",
    "how do you say",
)


_LANGUAGE_NAMES: frozenset[str] = frozenset(
    {
        "arabic",
        "chinese",
        "czech",
        "danish",
        "dutch",
        "english",
        "finnish",
        "french",
        "german",
        "greek",
        "hebrew",
        "hindi",
        "hungarian",
        "indonesian",
        "italian",
        "japanese",
        "korean",
        "mandarin",
        "norwegian",
        "polish",
        "portuguese",
        "russian",
        "spanish",
        "swedish",
        "turkish",
        "ukrainian",
        "vietnamese",
    }
)

# ISO-639-1 code -> human-readable language name, used to phrase the
# language-learning prompt ("for Russian" instead of "for ru").
_LANG_DISPLAY_NAMES: dict[str, str] = {
    "ar": "Arabic",
    "zh": "Chinese",
    "cs": "Czech",
    "da": "Danish",
    "nl": "Dutch",
    "en": "English",
    "fi": "Finnish",
    "fr": "French",
    "de": "German",
    "el": "Greek",
    "he": "Hebrew",
    "hi": "Hindi",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "es": "Spanish",
    "sv": "Swedish",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "vi": "Vietnamese",
}


def _lang_display_name(lang: str) -> str:
    """Return a human-readable language name for an ISO code/alias."""
    code = _normalize_lang(lang)
    return _LANG_DISPLAY_NAMES.get(code, lang or "the target language")


def _filter_foreign_language_teaching_entries(
    entries: list[dict[str, Any]],
    target_language: str,
) -> list[dict[str, Any]]:
    """Drop language-learning entries that teach a language other than
    *target_language* (backup issue #63).

    Deterministic: an entry is dropped only when its title+summary contains a
    non-target language name **and** a teaching signal phrase
    (``means`` / ``grammar`` / ``vocabulary`` / …).  Plain news that merely
    names a country or language is never dropped; non-language-learning
    domains (``target_language == ""``) pass through unchanged.
    """
    if not target_language:
        return entries
    target_norm = target_language.strip().lower()
    # Language names that are NOT the target (teaching *another* language).
    foreign_names = {name for name in _LANGUAGE_NAMES if name != target_norm}
    if not foreign_names:
        return entries

    kept: list[dict[str, Any]] = []
    dropped = 0
    for entry in entries:
        haystack = " ".join(
            filter(
                None,
                (
                    str(entry.get("title") or ""),
                    str(entry.get("summary") or ""),
                ),
            )
        ).lower()
        if not haystack:
            kept.append(entry)
            continue
        hit = False
        for name in foreign_names:
            if name not in haystack:
                continue
            for signal in _LANG_TEACHING_SIGNALS:
                if signal in haystack:
                    hit = True
                    break
            if hit:
                break
        if hit:
            dropped += 1
            logger.info(
                "Excluded foreign-language teaching entry from %s tutorial "
                "(teaches '%s' ≠ default_language)",
                target_language,
                next((n for n in foreign_names if n in haystack), "?"),
            )
        else:
            kept.append(entry)
    if dropped:
        logger.info(
            "Excluded %d foreign-language teaching entries (target '%s')",
            dropped,
            target_language,
        )
    return kept


# ---------------------------------------------------------------------------
# Content-ready notification helper
# ---------------------------------------------------------------------------


def _try_notify_content_ready(
    user_id: str,
    product_type: str,
    title: str,
) -> None:
    """Call :func:`autoinfo.notifications.notify_content_ready` with error suppression.

    Any failure is logged at DEBUG level — notification errors must never
    prevent the generated product from being returned to the caller.
    """
    try:
        from autoinfo.notifications import notify_content_ready  # noqa: PLC0415

        notify_content_ready(
            user_id=user_id,
            product_type=product_type,
            title=title,
        )
    except Exception:
        logger.debug(
            "Content-ready notification failed for user '%s' (%s)",
            user_id,
            product_type,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Product entry filtering (issue #298 — 3-layer guardrail, layer 1)
# ---------------------------------------------------------------------------
# Test/placeholder markers that identify non-production KB entries.  A product
# must never ship entries that are empty shells, test fixtures, or placeholder
# content — they pollute the LLM synthesis input AND the rendered body.

_TEST_TITLE_MARKERS: frozenset[str] = frozenset({
    "Get Test", "Entry A", "Entry B", "Entry C", "QA Article", "Test Entry",
    "Test", "test",
})
_TEST_TITLE_RE = re.compile(r"parity-t\d+|test\s+\d{4}-\d{2}-\d{2}", re.IGNORECASE)
_TEST_TITLE_SUBSTRINGS: tuple[str, ...] = (
    "validation import", "spotcheck", "test entry", "lorem ipsum",
    "placeholder", "test content",
)
_TEST_URL_MARKERS: tuple[str, ...] = (
    "example.org", "localhost", "127.0.0.1", ".local",
)
_TEST_SOURCE_PLATFORMS: frozenset[str] = frozenset({
    "fixture", "mock", "stub", "sample",
    "test-fixture", "test_fixture", "test-source", "test_source",
})

_NO_CONTENT_SUMMARY_RE: re.Pattern[str] = re.compile(
    r"^\s*(no\s+content\s+provided(?:\s+to\s+summarize)?\.?"
    r"|not\s+available\.?|n/?a\.?"
    r"|no\s+summary(?:\s+available)?\.?|no\s+content\.?)\s*$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Platform display-name mapping (issue #302 — ③)
# ---------------------------------------------------------------------------

_PLATFORM_DISPLAY_NAMES: dict[str, str] = {
    "pubmed": "PubMed",
    "semantic_scholar": "Semantic Scholar",
    "openalex": "OpenAlex",
    "sec_edgar": "SEC EDGAR",
    "rss": "RSS",
    "web": "Web",
    "api": "API",
    "arxiv": "arXiv",
    "dblp": "DBLP",
    "nyt": "NYT",
    "hackernews": "HackerNews",
    "reddit": "Reddit",
    "youtube": "YouTube",
    "bilibili": "Bilibili",
    "spotify": "Spotify",
    "apple_podcasts": "Apple Podcasts",
    "gdelt": "GDELT",
    "uspto": "USPTO",
    "crossref": "CrossRef",
    "unpaywall": "Unpaywall",
    "core": "CORE",
    "ssrn": "SSRN",
    "akshare": "AKShare",
    "edgar": "EDGAR",
}


def _platform_name(value: Any) -> str:
    """Map internal source_platform id to a display name (issue #302 — ③).

    Known ids are mapped to human-readable names; unknown ids fall back to
    the raw id.  Empty/None values return an em-dash.
    """
    if not value:
        return "\u2014"
    s = str(value).strip()
    if not s:
        return "\u2014"
    return _PLATFORM_DISPLAY_NAMES.get(s.lower(), s)


# Issue #138: product footers must not expose the internal domain slug
# (ai-commercial / financial-intelligence / medical-research) to end users.
# Map known demo-domain slugs to user-facing display names; unknown slugs
# fall back to a title-cased slug (medical-research -> Medical Research).
_DOMAIN_DISPLAY_NAMES: Final[dict[str, str]] = {
    # Issue #155: "Cross-Domain" is a PRODUCT label (the cross-domain
    # digest/report title), not a domain slug — the hyphen is intentional
    # and must survive the display-name mapping (the title-case fallback
    # would otherwise strip it to "Cross Domain").
    "Cross-Domain": "Cross-Domain",
    "medical-research": "Medical Research",
    "ai-commercial": "AI Commercial",
    "financial-intelligence": "Financial Intelligence",
    "tech-ai-developer": "Tech & AI",
    "language-learning": "Language Learning",
    "online-video": "Online Video",
    "financial-news": "Financial News",
    "online-education": "Online Education",
    "legal-compliance": "Legal & Compliance",
    "general-news": "General News",
    "gaming": "Gaming",
    "b2b": "B2B",
    "retail": "Retail",
    "english-learning": "English Learning",
    "french-learning": "French Learning",
    "hindi-learning": "Hindi Learning",
    "italian-learning": "Italian Learning",
    "korean-learning": "Korean Learning",
    "portuguese-learning": "Portuguese Learning",
    "russian-learning": "Russian Learning",
    "spanish-learning": "Spanish Learning",
}


def _domain_display_name(value: Any) -> str:
    """Return a user-facing display name for a domain slug (issue #138)."""
    if not value:
        return ""
    slug = str(value).strip()
    display = _DOMAIN_DISPLAY_NAMES.get(slug)
    if display:
        return display
    # Fallback: title-case each dash-separated segment.
    return slug.replace("-", " ").title()


def _user_source_label(ref: dict[str, Any]) -> str:
    """Return a user-facing source label for a References entry, or "" when
    none is safe to show (backup issue #91).

    ``ref.source_label`` is the host-derived user-facing name ("NPR",
    "Observador"); ``ref.source_platform`` is the raw internal feed id
    ("npr-news", "observador") that must NOT leak to end users.  The label
    is shown only when it exists and differs from the raw platform (i.e.
    ``_derive_source_label`` actually re-derived it); a generic/raw
    platform renders nothing so no internal id leaks.
    """
    label = str(ref.get("source_label") or "").strip()
    platform = str(ref.get("source_platform") or "").strip()
    if label and label.lower() != platform.lower():
        return label
    return ""


def _entry_source_cell(entry: dict[str, Any]) -> str:
    """Return a markdown Source cell for a product-table entry row (#167).

    Renders ``[LABEL](URL)`` when the entry carries a real http(s)
    ``source_url`` (LABEL is the derived user-facing source name —
    ``source_label`` or ``source_platform``, never the generic internal id),
    the bare LABEL when there is no URL, and ``""`` when neither exists.
    Synthetic non-http provenance (issue #189: compiled drafts carry a
    ``draft://<domain>/<entry>`` source_url so they never collide with the
    raw at G2 dedup) is rendered as the bare LABEL, never as a broken link.
    Used by the report and column sections tables so every row is traceable
    to its source.
    """
    url = str(entry.get("source_url") or "").strip()
    label = str(
        entry.get("source_label") or entry.get("source_platform") or ""
    ).strip()
    if url and url.startswith(("http://", "https://")):
        if not label:
            # No label but a real URL — show the host as the label.
            from urllib.parse import urlsplit

            label = urlsplit(url).hostname or url
        return f"[{label}]({url})"
    if label:
        return label
    return ""


# ---------------------------------------------------------------------------
# LLM leak detection (issue #302 — ①)
# ---------------------------------------------------------------------------

_LEAK_FENCED_JSON_RE: re.Pattern[str] = re.compile(
    r"```json\s*\n", re.IGNORECASE
)
_LEAK_JSON_PREFIX_RE: re.Pattern[str] = re.compile(
    r"^\s*\{\s*\"(?:title|entries|@type|digest_type)\"\s*:", re.IGNORECASE
)
_LEAK_PROMPT_ECHO_RE: re.Pattern[str] = re.compile(
    r"(?:^|\n)\s*(?:You are a |As an AI |You are an AI |System:\s|User:\s|Assistant:\s)",
    re.IGNORECASE,
)

# External LLM-library error text leaking into a product (issue #328):
# ANSI color escapes plus litellm / BerriAI markers.  Under high concurrency a
# failed LLM call can leave a raw error block (e.g. "Give Feedback / Get Help:
# https://github.com/BerriAI/litellm/issues/new\nLiteLLM.Info: If you need to
# debug this error, use `litellm._turn_on_debug()'") prepended to the rendered
# output, pushing the real title down.  The #294 guard never sniffed for this.
_LEAK_ERROR_TEXT_RE: re.Pattern[str] = re.compile(
    r"(?:\x1b\[[0-9;]*m|"
    r"Give Feedback / Get Help|"
    r"BerriAI|"
    r"LiteLLM\.Info|"
    r"litellm\._turn_on_debug|"
    r"litellm\.exceptions\.|"
    r"^Traceback \(most recent call last\):)",
    re.IGNORECASE | re.MULTILINE,
)


def _contains_raw_llm_leak(text: str) -> bool:
    """Heuristic check for raw LLM output leaking into a product (issue #302 — ①).

    Returns True when *text* contains fenced JSON blocks, raw JSON object
    prefixes, prompt-echo patterns, or external LLM-library error text
    (litellm/BerriAI/ANSI — issue #328) that indicate unreconstructed LLM
    output.  This is a defensive flag, not a hard block — the caller
    decides whether to warn or block.
    """
    if _LEAK_FENCED_JSON_RE.search(text):
        return True
    if _LEAK_JSON_PREFIX_RE.search(text):
        return True
    if _LEAK_PROMPT_ECHO_RE.search(text):
        return True
    if _LEAK_ERROR_TEXT_RE.search(text):
        return True
    return False


# CJK hard-check for non-bilingual products (issue #181).  English products for
# non-learning domains must not carry Chinese template-name / summary leaks.
# ``english-learning`` is the designed bilingual domain and is deliberately
# exempt.  A single CJK char with no real Chinese sentence reads as noise; we
# only warn past a small threshold so a stray ideograph in a code sample or a
# proper noun is not over-flagged.
_CJK_RE: re.Pattern[str] = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

# Domains exempt from the CJK leak check because bilingual output is by design.
# ``english-learning`` (and the *-learning family) is bilingual by design
# (#181); issue #190/193 added ``ai-commercial`` (36kr Chinese source, no
# forced default_language) and the ``cross-domain`` aggregate surface so the
# standard gate/warning commands never false-flag CJK there.
_CJK_EXEMPT_DOMAINS: frozenset[str] = frozenset(
    {"english-learning", "ai-commercial", "cross-domain"}
)


def _warn_cjk_leak(
    domain: str, product_type: str, rendered: str, threshold: int = 5
) -> int:
    """Warn when a non-exempt domain's product carries too many CJK chars.

    Counts CJK ideographs in *rendered* and logs a warning (issue #181) when
    the count exceeds *threshold*.  ``english-learning`` (bilingual by design)
    is skipped.  Returns the CJK char count so callers may filter if needed.
    """
    domain_key = (domain or "").strip().lower()
    if domain_key in _CJK_EXEMPT_DOMAINS:
        return 0
    count = len(_CJK_RE.findall(rendered))
    if count > threshold:
        logger.warning(
            "CJK leak in %s for domain '%s': %d CJK chars (threshold %d) "
            "— Chinese template name or summary leaked into an English product",
            product_type,
            domain,
            count,
            threshold,
        )
    return count


def _is_empty_summary(summary: str) -> bool:
    """True when *summary* is blank or a known placeholder string (issue #294).

    Returns True for empty, whitespace-only, or LLM-generated placeholder
    summaries like ``"No content provided to summarize."``.
    """
    stripped = summary.strip()
    if not stripped:
        return True
    return bool(_NO_CONTENT_SUMMARY_RE.match(stripped))


def _is_empty_content(content: Any) -> bool:
    """True when *content* is blank (no real body text).

    Issue #326: the product pipeline enriches real KB entries with their
    ``content`` (body loaded from the KB markdown file).  An entry whose
    ``content`` is missing, empty, or whitespace-only has no extractable body
    and is treated as an empty entry (like issue #294's empty summaries).  A
    non-empty ``content`` signals a real Draft/Wiki entry even when the DB
    ``summary`` column is empty.
    """
    if content is None:
        return True
    stripped = str(content).strip()
    return not stripped


def _enrich_entry_content(entry: dict[str, Any]) -> dict[str, Any]:
    """Load an entry's body ``content`` from its KB markdown file when the
    DB ``summary`` column is empty (issue #326).

    Real Draft/Wiki entries store their extracted text under
    ``## Original Content`` in the KB markdown file, but the SQLite
    ``entries`` table has no ``content`` column and its ``summary`` column
    may be empty.  ``_is_test_entry`` would otherwise drop these real entries
    as "empty-summary" (issue #294) — leaving the column Deep Dive / report
    Sections empty.  This helper reads the file body so ``_is_empty_content``
    sees real content and the entry is kept.

    The file is only read when the summary is empty (the common case has a
    non-empty summary and skips the I/O entirely).
    """
    if not _is_empty_summary(str(entry.get("summary") or "")):
        return entry
    file_path = entry.get("file_path")
    if not file_path or not Path(str(file_path)).is_file():
        return entry
    try:
        raw = Path(str(file_path)).read_text(encoding="utf-8")
    except OSError:
        return entry
    # Prefer the "## Original Content" section; fall back to the raw body.
    marker = "## Original Content"
    if marker in raw:
        body = raw.split(marker, 1)[1].strip()
    else:
        body = raw.strip()
    if body:
        entry["content"] = body
    return entry


def _enrich_product_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich product entries with file ``content`` (issue #326).

    Applied after entry loading and before ``_filter_product_entries`` so real
    Draft/Wiki entries with an empty DB summary but file content survive the
    empty-entry guard.
    """
    return [_enrich_entry_content(dict(e)) if isinstance(e, dict) else e for e in entries]


def _entry_custom_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Parse an entry's ``custom_fields`` (JSON string or dict) into a dict."""
    raw = entry.get("custom_fields")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _is_test_entry(entry: dict[str, Any]) -> bool:
    """True when *entry* carries a test/placeholder marker (issue #298).

    Also returns True for entries with empty/placeholder summary
    (issue #294) — these produce blank cells or "No content provided"
    strings in rendered products.
    """
    title = str(entry.get("title") or "").strip()
    summary = str(entry.get("summary") or "").strip()
    source_url = str(entry.get("source_url") or "").strip()
    source_platform = str(entry.get("source_platform") or "").strip()

    # (a) empty title AND empty summary -> no usable content
    if not title and not summary:
        return True
    # (a2) empty/placeholder summary -> only treated as a test/empty entry
    # when there is no real body content either.  A real Draft/Wiki entry
    # whose body lives in the KB markdown file (loaded into the entry dict's
    # ``content`` field by the product pipeline) but whose DB ``summary``
    # column is empty is meaningful and must NOT be dropped (issue #326).
    # Entries without a ``content`` field (never enriched from a file) keep
    # the #294 behaviour: empty summary -> dropped.
    if _is_empty_summary(summary) and _is_empty_content(entry.get("content")):
        return True
    # (a3) summary contains lorem ipsum -> placeholder text (issue #293)
    if "lorem ipsum" in summary.lower():
        return True
    # (b) URL placeholder markers
    if any(marker in source_url.lower() for marker in _TEST_URL_MARKERS):
        return True
    # (b) title markers
    if title in _TEST_TITLE_MARKERS:
        return True
    if _TEST_TITLE_RE.search(title):
        return True
    title_lower = title.lower()
    if any(sub in title_lower for sub in _TEST_TITLE_SUBSTRINGS):
        return True
    # (c) custom_fields.test / status markers (issue #293)
    cf = _entry_custom_fields(entry)
    if cf.get("test") is True:
        return True
    cf_status = str(cf.get("status") or "").strip().lower()
    if cf_status in ("test", "placeholder", "mock", "sample", "demo"):
        return True
    # (d) known test source platforms
    if source_platform.lower() in _TEST_SOURCE_PLATFORMS:
        return True
    return False


# Placeholder digest draft patterns (issue #184).
#
# ``create_kb_draft`` can produce a SINGLE-source placeholder when the digest
# entity extraction yielded no per-article rows: the draft carries a generic
# placeholder title ("AI-commercial weekly: <domain> digest") and a truncated
# summary beginning with "本期" and containing "要点" ("本期核心要点: ..." /
# "本期...要点: ...").  Such single-source drafts carry source_ids of length 1
# so the multi-source check above lets them escape — but they are still
# synthesized workspace digest artifacts, not news items, and must be excluded
# from the product stream the same way (#184).
#
# Placeholder detection is deterministic (no LLM): the truncated summary
# starts with "本期" and contains "要点"; or the title carries a digest-flag
# token like "weekly:" followed by content, or a domain template name
# ("情报"/"周报"/"素材"/"前沿") followed by a digit.  These markers are chosen
# to be specific enough that real news headlines (which rarely embed
# "本期"+"要点", a bare "weekly:" template token, or a template name + digit)
# are never misclassified.
_SUMMARY_PLACEHOLDER_RE = re.compile(r"^本期.*要点")
_TITLE_PLACEHOLDER_RE = re.compile(
    r"(weekly:|情报\s*\d|周报\s*\d|素材\s*\d|前沿\s*\d)", re.IGNORECASE
)


def _is_synthesized_digest_entry(entry: dict[str, Any]) -> bool:
    """True when *entry* is a synthesized digest artifact (issues #178/#184).

    ``create_kb_draft(raw_ids, ...)`` compiles MULTIPLE 01-Raw entries into a
    single 02-Draft (later promotable to 03-Wiki) digest entry whose
    frontmatter records the source ids.  Such entries are production
    workspace artifacts, NOT single news items — surfacing them in the normal
    product stream renders a fake "one source, one title" news row with a
    single (misattributed) source_url.  Returns True iff tier is 02-Draft or
    03-Wiki AND either:

    * custom_fields marks >1 distinct source raw id (``source_ids`` array, or
      comma-bearing ``source_raw_ids`` for legacy drafts), OR
    * the entry carries single-source placeholder artifact markers (a
      truncated "本期...要点" summary, or a digest-flag placeholder title) —
      the #184 leak path where a single-source placeholder draft escapes the
      multi-source check and would otherwise reach the product stream.

    Deterministic, no LLM.
    """
    tier = str(entry.get("tier") or "").strip()
    if tier not in ("02-Draft", "03-Wiki"):
        return False
    cf = _entry_custom_fields(entry)
    source_ids = cf.get("source_ids")
    if isinstance(source_ids, list):
        distinct = {str(i) for i in source_ids if str(i).strip()}
        if len(distinct) > 1:
            return True
    else:
        source_raw = str(cf.get("source_raw_ids") or "").strip()
        if "," in source_raw or "，" in source_raw:
            if len({p for p in re.split(r"[,\s，]+", source_raw) if p}) > 1:
                return True
    # Issue #184: placeholder artifact markers (single-source placeholder
    # drafts escape the multi-source check above).  Only the explicit digest
    # flag/template patterns count — real entries at rest aren't touched.
    summary = str(entry.get("summary") or "").strip()
    if summary and _SUMMARY_PLACEHOLDER_RE.search(summary):
        return True
    title = str(entry.get("title") or "").strip()
    if title and _TITLE_PLACEHOLDER_RE.search(title):
        return True
    return False


def _filter_product_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop empty / test / placeholder entries from a product's entry list.

    Layer 1 of the 3-layer guardrail (issue #298): the synthesis input AND the
    rendered body must be clean.  Applied by every product generator
    (digest/report/tutorial/presentation) BEFORE synthesis and BEFORE render.
    """
    kept: list[dict[str, Any]] = []
    dropped = 0
    for entry in entries:
        if _is_test_entry(entry):
            dropped += 1
            continue
        # Issue #178: synthesized multi-source digest entries (02-Draft /
        # 03-Wiki compiled from >1 raw) are production-workspace artifacts,
        # not news items — excluding them keeps the product stream clean of
        # fake single-source rows and one-source-many-titles misattribution.
        if _is_synthesized_digest_entry(entry):
            dropped += 1
            continue
        kept.append(entry)
    if dropped:
        logger.info("Filtered %d test/empty/synthesized entries from product input", dropped)
    return kept


# ---------------------------------------------------------------------------
# Near-duplicate convergence (backup issue #69)
# ---------------------------------------------------------------------------
# Cross-language / cross-source same-event duplicates (e.g. "Dolly Parton
# has died" vs "Mort de la star américaine Dolly Parton") are invisible to
# the char-level G2Dedup similarity gate, so the same event can be ingested
# many times across domains/languages and flood every product that consumes
# the KB.  This product-layer convergence clusters entries that share a
# distinctive proper-noun signature within a short time window and keeps ONE
# representative per cluster — non-destructive (entries stay in the KB; only
# the product picks a representative) and deterministic (no LLM).
# ---------------------------------------------------------------------------

# G2Dedup's fuzzy-title threshold (quality.py): title similarity >=0.85 is
# flagged duplicate at ingest.  The stored dedup_status fast-path below only
# trusts the flag when the two titles actually meet this bar — a bare
# dedup_status alone is not a same-event signal (a re-collection can flag
# every entry, and multi-angle reports of one event may all carry it).
_NEAR_DUP_CHAR_SIM_MAX = 0.85

# The proper-noun signature extractor and the cross-language death/obituary
# lexicon live in :mod:`autoinfo.textutil`, shared with the collection-layer
# cross-domain dedup (backup issue #109) so the two never drift.  Re-exported
# here so existing callers/tests keep working.
from autoinfo.textutil import (  # noqa: E402  (import at module top)
    _NEAR_DUP_WINDOW_DAYS,
    _extract_proper_nouns,
    _has_death_event_word,
)


def _converge_near_duplicates(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse same-event near-duplicates to one representative per cluster.

    Cluster rule: two entries belong to the same event when they share a
    distinctive proper-noun phrase (≥2-word capitalized sequence) within
    :data:`_NEAR_DUP_WINDOW_DAYS` days AND carry at least one secondary
    signal — an already-stored ``dedup_status == "duplicate"`` **corroborated
    by ≥0.85 title similarity** (G2Dedup's fuzzy-title threshold — a bare
    dedup flag alone is not a same-event signal), a second
    shared proper noun, or (backup issue #73) a canonical death/obituary event
    word in BOTH titles, each co-occurring with the shared proper noun in its
    own title.  Identical
    ``source_url`` is never merged (syndication is intentional).

    The representative is the highest ``relevance_score`` entry of the
    cluster (tie-break: earliest ``collected_at``, then ``entry_id``) — the
    order in which candidates are promoted to representatives.  Returns a
    NEW list; input dicts are never mutated and never dropped from the KB.
    """
    from autoinfo.output import datetime  # noqa: PLC0415 - package seam
    if not entries:
        return []
    nouns_by_key: dict[int, set[str]] = {}
    for idx, entry in enumerate(entries):
        nouns_by_key[idx] = set(_extract_proper_nouns(str(entry.get("title") or "")))

    def _sort_key(entry: dict[str, Any]) -> tuple[float, str, str]:
        relevance = float(entry.get("relevance_score") or 0.0)
        collected = str(entry.get("collected_at") or "")
        eid = str(entry.get("entry_id") or "")
        return (-relevance, collected, eid)

    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            return None

    def _within_window(rep: dict[str, Any], entry: dict[str, Any]) -> bool:
        rep_dt = _parse_dt(rep.get("collected_at"))
        entry_dt = _parse_dt(entry.get("collected_at"))
        if rep_dt is None or entry_dt is None:
            # Unparseable/missing dates: skip the window clause (conservative —
            # allow merge on the other signals).
            return True
        return abs((entry_dt - rep_dt).days) <= _NEAR_DUP_WINDOW_DAYS

    def _shares_noun(rep_idx: int, entry_idx: int) -> bool:
        rep_nouns = nouns_by_key.get(rep_idx, set())
        entry_nouns = nouns_by_key.get(entry_idx, set())
        if rep_nouns & entry_nouns:
            return True
        # Phrase subsumption: "Muere Dolly Parton" contains "Dolly Parton"
        # as a whole-word substring — same signature, different leading verb
        # (title-initial capitalized verb in Romance languages).
        for a in rep_nouns:
            for b in entry_nouns:
                if a in b or b in a:
                    return True
        return False

    def _death_event_signal(rep: dict[str, Any], entry: dict[str, Any]) -> bool:
        """Death/obituary event-word co-occurrence signal (backup issue #73).

        Two reworded reports of the SAME death event each carry a canonical
        death event word in their own title, in the language of that title,
        and each event word co-occurs with a shared proper noun in the same
        title.  Requiring the word in BOTH titles — not either — keeps a
        tribute/feature title that merely mentions the deceased out of the
        obituary cluster.
        """
        rep_title = str(rep.get("title") or "").strip()
        entry_title = str(entry.get("title") or "").strip()
        if not rep_title or not entry_title:
            return False
        rep_idx = next(
            (i for i, e in enumerate(entries) if e is rep), -1
        )
        entry_idx = next(
            (i for i, e in enumerate(entries) if e is entry), -1
        )
        if rep_idx < 0 or entry_idx < 0:
            return False
        rep_nouns = nouns_by_key.get(rep_idx, set())
        entry_nouns = nouns_by_key.get(entry_idx, set())
        shared: set[str] = set(rep_nouns) & set(entry_nouns)
        for a in rep_nouns:
            for b in entry_nouns:
                if a in b:
                    shared.add(a)
                if b in a:
                    shared.add(b)
        if not shared:
            return False
        # The event word must co-occur with the shared proper noun in the
        # same title — satisfied when a shared phrase is a substring of both.
        if not any(noun in rep_title for noun in shared):
            return False
        if not any(noun in entry_title for noun in shared):
            return False
        return (
            _has_death_event_word(rep_title, rep.get("language"))
            and _has_death_event_word(entry_title, entry.get("language"))
        )

    def _secondary_signal(rep: dict[str, Any], entry: dict[str, Any]) -> bool:
        a = (str(rep.get("title") or "")).lower()
        b = (str(entry.get("title") or "")).lower()
        # The stored dedup_status fast-path is ONLY trustworthy when it
        # corroborates its own G2 premise: dedup_status="duplicate" is set by
        # G2Dedup for URL/PMID/DOI/fuzzy-title matches, and the fuzzy-title
        # verdict fires at >=0.85 title similarity (quality.py G2Dedup).  A
        # bare dedup_status alone is NOT a same-event signal — a re-collection
        # can flag every entry duplicate, and multi-angle reports of one event
        # (obituary + tribute + song-list) may all carry the flag while being
        # distinct stories.  Requiring >=0.85 similarity confines the fast-path
        # to true near-identical duplicates and forces multi-angle merges
        # through the noun/event-word signals instead (backup issues #69/#73).
        if (
            a
            and b
            and str(entry.get("dedup_status") or "").lower() == "duplicate"
            and SequenceMatcher(None, a, b).ratio() >= _NEAR_DUP_CHAR_SIM_MAX
        ):
            return True
        rep_idx = next(
            (i for i, e in enumerate(entries) if e is rep), -1
        )
        entry_idx = next(
            (i for i, e in enumerate(entries) if e is entry), -1
        )
        if rep_idx >= 0 and entry_idx >= 0:
            shared = nouns_by_key.get(rep_idx, set()) & nouns_by_key.get(entry_idx, set())
            if len(shared) >= 2:
                return True
        return _death_event_signal(rep, entry)

    reps: list[dict[str, Any]] = []
    dropped = 0
    for entry in sorted(entries, key=_sort_key):
        entry_idx = entries.index(entry)
        merged = False
        for rep in reps:
            rep_idx = entries.index(rep)
            if str(rep.get("source_url") or "") == str(entry.get("source_url") or ""):
                continue  # syndication — never merge identical URLs
            if not _shares_noun(rep_idx, entry_idx):
                continue
            if not _within_window(rep, entry):
                continue
            if not _secondary_signal(rep, entry):
                continue
            merged = True
            dropped += 1
            logger.info(
                "Converged near-duplicate entry '%s' into representative '%s'",
                entry.get("title", "")[:60],
                rep.get("title", "")[:60],
            )
            break
        if not merged:
            reps.append(entry)
    if dropped:
        logger.info("Converged %d near-duplicate entries in product input", dropped)
    return reps


def _filter_digest_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run the digest's content filter chain over a candidate entry set.

    Archive/deprecated exclusion, test/empty-entry filtering and
    near-duplicate convergence — the same chain the digest applies to a
    window query, shared so the #83 full-domain fallback runs identical
    filters over its candidate set (only non-archived active content is
    ever recovered).  Deterministic, no LLM.
    """
    active: list[dict[str, Any]] = []
    for entry in entries:
        cf = entry.get("custom_fields") or "{}"
        try:
            cf_dict = json.loads(cf) if isinstance(cf, str) else dict(cf)
        except (json.JSONDecodeError, TypeError):
            cf_dict = {}
        if cf_dict.get("status") in ("archived", "deprecated"):
            continue
        active.append(entry)
    return _converge_near_duplicates(
        _filter_product_entries(_enrich_product_entries(active))
    )


_LANG_ALIASES: dict[str, str] = {
    "zh-cn": "zh",
    "zh-hans": "zh",
    "zh-hant": "zh",
    "zh-tw": "zh",
    "zh-hk": "zh",
    "cn": "zh",
    "中文": "zh",
    "chinese": "zh",
    "en-us": "en",
    "en-gb": "en",
    "eng": "en",
    "english": "en",
}


def _normalize_lang(value: str) -> str:
    """Normalize an ISO-639/alias language tag to the canonical 2-letter code.

    ``zh_CN``, ``en-US``, ``中文``, ``chinese`` → ``zh`` / ``en``.  Unknown
    values pass through lowercased.
    """
    v = (value or "").strip().replace("_", "-").replace(" ", "-").lower()
    if not v:
        return ""
    return _LANG_ALIASES.get(v, v.split("-")[0])


def _filter_entries_by_language(
    entries: list[dict[str, Any]], language: str
) -> list[dict[str, Any]]:
    """Keep only entries whose ``language`` field matches *language* (issue #309).

    *language* is normalized via :func:`_normalize_lang`; matching is done on
    the canonical code so ``"zh"`` matches ``zh_CN``/``中文`` and ``"en"``
    matches ``en-US``/``english``.  Entries with an empty/unknown language are
    dropped when a language filter is active (an unfiltered product should not
    silently mix languages).  Returns the input unchanged when *language* is
    empty.
    """
    target = _normalize_lang(language)
    if not target:
        return entries
    kept: list[dict[str, Any]] = []
    dropped = 0
    for entry in entries:
        entry_lang = _normalize_lang(str(entry.get("language") or ""))
        if entry_lang == target:
            kept.append(entry)
        else:
            dropped += 1
    if dropped:
        logger.info(
            "Excluded %d entries from product input for language='%s'",
            dropped, target,
        )
    return kept


# Issue #53: a stale seed/config ``default_language`` that mismatches the real
# data distribution (e.g. a ``zh`` seed on an English domain) can collapse a
# healthy product input to an empty/near-empty shell.  ``_LANGUAGE_COLLAPSE_*``
# bound the anti-collapse safety net in
# :func:`_filter_entries_by_language_product_safe`: input of at least
# ``_LANGUAGE_COLLAPSE_MIN_INPUT`` entries that filters down to at most
# ``_LANGUAGE_COLLAPSE_MAX_KEPT`` is treated as a stale-language collapse.
_LANGUAGE_COLLAPSE_MIN_INPUT = 3
_LANGUAGE_COLLAPSE_MAX_KEPT = 1


def _filter_entries_by_language_product_safe(
    entries: list[dict[str, Any]], language: str
) -> tuple[list[dict[str, Any]], bool]:
    """Language filter with an anti-collapse safety net (issue #53).

    Applying *language* at the product level must never silently wipe out a
    domain's primary corpus: when the plain filter would keep at most
    ``_LANGUAGE_COLLAPSE_MAX_KEPT`` entries out of an input of
    ``>= _LANGUAGE_COLLAPSE_MIN_INPUT`` — a resolved (seed or configured)
    language that no longer matches the domain's actual data distribution —
    fall back to the FULL unfiltered input and log a warning instead of
    shipping an empty/near-empty product.

    Returns ``(entries, collapsed)``: ``collapsed`` True means *entries* is the
    unfiltered input (the safety net already fired and logged); False means
    *entries* is the plain filtered result.  Inputs smaller than
    ``_LANGUAGE_COLLAPSE_MIN_INPUT`` are too small to judge and pass through
    the plain filter untouched (keeps the pinned #8 ai-commercial two-entry
    enforcement intact).
    """
    filtered = _filter_entries_by_language(entries, language)
    if (
        len(entries) >= _LANGUAGE_COLLAPSE_MIN_INPUT
        and len(filtered) <= _LANGUAGE_COLLAPSE_MAX_KEPT
    ):
        logger.warning(
            "Language filter '%s' would reduce %d inputs to %d — treating the "
            "resolved language as stale and falling back to unfiltered input "
            "(issue #53)",
            language, len(entries), len(filtered),
        )
        return entries, True
    return filtered, False


def _resolve_gloss_language(domain: str, default: str = "en") -> str:
    """Resolve the gloss/learner language for a language-learning domain.

    Issue #162: tutorial Vocabulary translations must be in the learner's
    native language, not whatever the LLM invents (observed: Korean glosses
    in an english-learning tutorial).  Reads the domain config's
    ``gloss_language`` (e.g. ``zh`` for Simplified Chinese); falls back to
    *default* (``en``) when unset.
    """
    from autoinfo.output import get_config_path, load_config  # noqa: PLC0415 - package seam
    try:
        config_path = get_config_path()
        if config_path and config_path.is_file():
            config = load_config(config_path)
            for d in config.domains:
                if d.name == domain and d.gloss_language:
                    return str(d.gloss_language).strip() or default
    except Exception:
        pass
    return default


def _resolve_effective_language(
    language: str, domain: str, *, cross_domain: bool = False
) -> str:
    """Resolve the effective language for a product (issue #317).
    Precedence:
    1. An explicit *language* param always wins.
    2. Otherwise, for a single-domain product, fall back to the domain's
       configured ``default_language`` (so mixed-language domains like
       ai-commercial come out single-language without manual params).
    3. Otherwise ``""`` — no filtering (legacy behavior).

    Seed fallback (issue #8): when a project config file EXISTS but its
    domain block carries no ``default_language`` key at all (projects
    initialized before the field existed — ``init`` only propagates it for
    NEW domains), fall back to the demo-domain seed
    ``src/autoinfo/data/domains/<domain>/sources.yaml`` so live surfaces
    come out single-language immediately without a config migration.  An
    explicitly declared (even empty) value always wins — empty means "no
    filtering", backward compatible.  A project with NO config file at all
    stays ``""`` (no filtering) — seeding never engages on a missing config.

    For a cross-domain product (*cross_domain* True) we never silently pick
    one domain's default across multiple domains: an explicit param wins,
    otherwise no filtering.
    """
    from autoinfo.output import (  # noqa: PLC0415 - package seam
        _seed_domain_default_language,
        get_config_path,
        load_config,
    )
    if language:
        return language
    if cross_domain:
        return ""
    config_path = get_config_path()
    if config_path is None or not config_path.is_file():
        return ""
    try:
        config = load_config(config_path)
    except Exception:
        return ""
    for d in config.domains:
        if d.name == domain:
            if _config_declares_default_language(config_path, domain):
                return d.default_language or ""
            break
    return _seed_domain_default_language(domain)


def _config_declares_default_language(config_path: Path, domain: str) -> bool:
    """True when the raw config YAML declares a ``default_language`` key for
    *domain* (even an empty value).

    The parsed :class:`DomainConfig` cannot distinguish "key present but
    empty" from "key missing" — both parse to ``""`` — so the raw dict is
    consulted for the seed-fallback decision (issue #8).
    """
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    for d in raw.get("domains", []):
        if d.get("name") == domain:
            return "default_language" in d
    return False


def _seed_domain_default_language(domain: str) -> str:
    """Demo-domain seed fallback for ``default_language`` (issue #8).

    Reads ``src/autoinfo/data/domains/<domain>/sources.yaml`` (the same seed
    ``init`` uses) so existing projects whose runtime config predates the
    field still come out single-language without a config migration.
    Returns ``""`` when the seed file is absent or carries no
    ``default_language``.
    """
    from autoinfo.output import _DEMO_DOMAINS_DIR  # noqa: PLC0415 - package seam
    seed_path = _DEMO_DOMAINS_DIR / domain / "sources.yaml"
    if not seed_path.is_file():
        return ""
    try:
        with open(seed_path, encoding="utf-8") as f:
            seed = yaml.safe_load(f) or {}
    except Exception:
        return ""
    return str(seed.get("default_language") or "")


def _cross_domain_shared_language(domains: list[str]) -> str:
    """Return the shared non-bilingual default language across *domains*.

    Issue #186: a cross-domain report (e.g. ai-commercial + financial-
    intelligence, both ``default_language: en``) must produce a
    language-coherent product.  When EVERY contributing domain shares the
    same non-empty ``default_language`` and none is a bilingual-by-design
    language-learning domain, that shared language is the product language —
    so Chinese raw entries (36kr) are filtered out of an English report.
    Returns ``""`` when domains disagree, any default is empty, or any domain
    is language-learning (bilingual by design) — no filtering in those cases.
    """
    if not domains:
        return ""
    from autoinfo.output import _is_lang_learning_domain

    langs: set[str] = set()
    for d in domains:
        if _is_lang_learning_domain(d):
            return ""
        lang = _seed_domain_default_language(d)
        if not lang:
            return ""
        langs.add(_normalize_lang(lang))
    if len(langs) == 1:
        return next(iter(langs))
    return ""


def _get_domain_exclude_keywords(domain: str) -> list[str]:
    """Load the ``exclude_keywords`` list for *domain* from the project config.

    Returns an empty list when the config cannot be loaded or the domain is
    not found — an empty list means "no filtering" (backward compatible).
    Mirrors the config-loading pattern of :func:`_get_domain_source_configs`.

    Seed fallback (issue #319): when the runtime config's domain carries no
    ``exclude_keywords`` key at all (projects initialized before the field
    existed — ``init`` only propagates it for NEW domains), fall back to the
    demo-domain seed ``src/autoinfo/data/domains/<domain>/sources.yaml`` so
    live surfaces filter immediately without a config migration.  An
    explicitly declared (even empty) list always wins — backward compatible
    "no filtering".  The seed file is read once per call (tiny YAML); an
    absent file yields ``[]``.
    """
    from autoinfo.output import get_config_path, load_config  # noqa: PLC0415 - package seam
    config_path = get_config_path()
    if config_path is None or not config_path.is_file():
        return _seed_domain_exclude_keywords(domain)
    try:
        config = load_config(config_path)
    except Exception:
        return _seed_domain_exclude_keywords(domain)
    for d in config.domains:
        if d.name == domain:
            if _config_declares_exclude_keywords(config_path, domain):
                return list(d.exclude_keywords)
            break
    return _seed_domain_exclude_keywords(domain)


def _config_declares_exclude_keywords(config_path: Path, domain: str) -> bool:
    """True when the raw config YAML declares an ``exclude_keywords`` key for
    *domain* (even an empty list).

    The parsed :class:`DomainConfig` cannot distinguish "key present but
    empty" from "key missing" — both parse to ``[]`` — so the raw dict is
    consulted for the seed-fallback decision (issue #319).
    """
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    for d in raw.get("domains", []):
        if d.get("name") == domain:
            return "exclude_keywords" in d
    return False


def _seed_domain_exclude_keywords(domain: str) -> list[str]:
    """Demo-domain seed fallback for ``exclude_keywords`` (issue #319).

    Reads ``src/autoinfo/data/domains/<domain>/sources.yaml`` (the same seed
    ``init`` uses) so existing projects whose runtime config predates the
    field still filter cross-domain noise without a config migration.
    Returns ``[]`` when the seed file is absent or unreadable.
    """
    from autoinfo.output import _DEMO_DOMAINS_DIR  # noqa: PLC0415 - package seam
    seed_path = _DEMO_DOMAINS_DIR / domain / "sources.yaml"
    if not seed_path.is_file():
        return []
    try:
        with open(seed_path, encoding="utf-8") as f:
            seed = yaml.safe_load(f) or {}
    except Exception:
        return []
    return list(seed.get("exclude_keywords") or [])


def _seed_domain_relevance_floor(domain: str) -> int:
    """Demo-domain seed fallback for ``min_product_relevance`` (issue #166).

    Reads ``src/autoinfo/data/domains/<domain>/sources.yaml`` so existing
    projects filter off-topic entries at product aggregation without a config
    migration (same pattern as the exclude_keywords seed, #319).  Returns 0
    (disabled) when the seed file is absent or declares no floor.
    """
    from autoinfo.output import _DEMO_DOMAINS_DIR  # noqa: PLC0415 - package seam
    seed_path = _DEMO_DOMAINS_DIR / domain / "sources.yaml"
    if not seed_path.is_file():
        return 0
    try:
        with open(seed_path, encoding="utf-8") as f:
            seed = yaml.safe_load(f) or {}
    except Exception:
        return 0
    try:
        return int(seed.get("min_product_relevance") or 0)
    except (TypeError, ValueError):
        return 0


def _get_domain_relevance_floor(domain: str) -> int:
    """Load the per-domain product relevance floor (issue #166).

    Reads ``min_product_relevance`` from the project config's domain block;
    when the config declares no ``min_product_relevance`` key for the domain
    (projects initialized before the field existed), falls back to the
    demo-domain seed (see :func:`_seed_domain_relevance_floor`) so live
    surfaces filter immediately without a config migration — the same
    declare-or-seed pattern as exclude_keywords (#319).  An explicitly
    declared value always wins.  Returns 0 (disabled) when unset everywhere.
    """
    from autoinfo.output import get_config_path, load_config  # noqa: PLC0415 - package seam
    config_path = get_config_path()
    if config_path and config_path.is_file():
        try:
            config = load_config(config_path)
            for d in config.domains:
                if d.name == domain:
                    if _config_declares_relevance_floor(config_path, domain):
                        return int(d.min_product_relevance or 0)
                    break
        except Exception:
            return _seed_domain_relevance_floor(domain)
    return _seed_domain_relevance_floor(domain)


def _config_declares_relevance_floor(config_path: Path, domain: str) -> bool:
    """True when the raw config YAML declares a ``min_product_relevance`` key
    for *domain* (even a zero value).  Mirrors
    :func:`_config_declares_exclude_keywords` (issue #166/#319)."""
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    for d in raw.get("domains", []):
        if d.get("name") == domain:
            return "min_product_relevance" in d
    return False


def _entry_matches_exclude_keywords(
    entry: dict[str, Any], keywords: list[str]
) -> bool:
    """Return True when any excluded keyword appears in the entry's content.

    Matching is a deterministic substring check (casefold for latin, CJK-aware)
    over the entry's title + summary + tags.  Tags may arrive as a JSON string
    (SQLite) or a list — the same parsing pattern as ``_build_digest_llm_prompt``.
    """
    if not keywords:
        return False
    title = str(entry.get("title") or "")
    summary = str(entry.get("summary") or "")
    tags_raw = entry.get("tags", "")
    if isinstance(tags_raw, str):
        try:
            tags_list = json.loads(tags_raw)
        except (json.JSONDecodeError, TypeError):
            tags_list = [tags_raw] if tags_raw else []
    elif isinstance(tags_raw, list):
        tags_list = tags_raw
    else:
        tags_list = []
    tags_text = " ".join(str(t) for t in tags_list)
    haystack = f"{title}\n{summary}\n{tags_text}".casefold()
    return any(kw and kw.casefold() in haystack for kw in keywords)


def _filter_entries_by_domain_exclusions(
    entries: list[dict[str, Any]], domain: str
) -> list[dict[str, Any]]:
    """Per-domain product-admission filter: exclude_keywords blacklist +
    relevance floor (#319 + #166).

    Issue #319: ai-commercial digests contained medical entries (贝达药业,
    EyePoint DURAVYU) that passed the G1-G3 relevance gates.  This is a
    product-generation-layer filter (NOT a gate change): each entry is checked
    against the ``exclude_keywords`` of its OWN domain (entry dicts carry
    ``domain``; falls back to *domain* when absent), so a cross-domain digest
    filters per-entry.  Matching is deterministic — substring on
    title+summary+tags, no LLM involvement.

    Issue #166: additionally drops entries whose stored ``relevance_score``
    is below the domain's ``min_product_relevance`` floor — catching off-topic
    items (horse RCTs, personal-finance Q&A) the substring blacklist cannot
    express.  Entries WITHOUT a stored relevance_score pass (fail-open, so
    curated/imported/promoted content and unseeded domains are unaffected).
    Returns the input unchanged when no domain declares exclusions or a floor.
    """
    from autoinfo.output import (  # noqa: PLC0415 - package seam
        _get_domain_exclude_keywords,
        _get_domain_relevance_floor,
    )
    if not entries:
        return entries
    exclude_by_domain: dict[str, list[str]] = {}
    floor_by_domain: dict[str, int] = {}
    kept: list[dict[str, Any]] = []
    dropped = 0
    for entry in entries:
        entry_domain = str(entry.get("domain") or domain)
        if entry_domain not in exclude_by_domain:
            exclude_by_domain[entry_domain] = _get_domain_exclude_keywords(
                entry_domain
            )
            floor_by_domain[entry_domain] = _get_domain_relevance_floor(
                entry_domain
            )
        keywords = exclude_by_domain[entry_domain]
        if keywords and _entry_matches_exclude_keywords(entry, keywords):
            dropped += 1
            continue
        floor = floor_by_domain[entry_domain]
        if floor > 0:
            raw_score = entry.get("relevance_score")
            if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool):
                try:
                    if float(raw_score) < floor:
                        dropped += 1
                        continue
                except (TypeError, ValueError):
                    pass  # non-numeric score -> fail-open (keep)
            # absent/None/NaN score -> fail-open (keep)
        kept.append(entry)
    if dropped:
        logger.info(
            "Excluded %d entries from product input for domain '%s' via "
            "exclude_keywords / relevance floor (product admission filter)",
            dropped, domain,
        )
    return kept
