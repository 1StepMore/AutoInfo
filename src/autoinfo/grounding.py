"""Deterministic claim-grounding primitives for delivered products.

One concept, two consumers:

- :mod:`autoinfo.output` filters the per-product LLM synthesis so a narrative
  field cannot introduce an entity absent from the entries it was handed.  The
  #179/#191 no-fabrication discipline already rides every synthesis prompt as
  an *instruction*; this module makes the same discipline *checkable* without
  building a provenance platform: an entity that appears in the synthesis and
  in no supplied entry is a detectable condition, and it is detected here.
- :mod:`autoinfo.quality` (D2, delivery time) fails a rendered product loud
  when its own narrative names an item the rest of the body does not contain.

Precision model
---------------
Calibrated against real delivered products, and deliberately the same shape
``scripts/quality_gate.py`` uses for C6 so the dev-side and delivery-side
verdicts agree.

*Candidate classes* — two, both Title-Case:

1. **Multi-token phrase** — 1-6 consecutive Title-Case tokens
   (``OpenAI Jalapeño``, ``Nvidia Blackwell``).  Any such run is a claim.
2. **Single token, not sentence-initial** — ``Jalapeño chip`` mid-sentence is
   a claim; ``Jalapeño`` opening a sentence is not (it may be a fronted name,
   and C6 already declines single-word candidates).

Single sentence-initial capitalized words are never candidates, and neither
are tokens inside URLs or markdown links.

*Support test* — a candidate is **supported** when the corpus contains it
verbatim (case-folded) OR contains *every* one of its content tokens.  The
token test absorbs the paraphrases that matter in practice — possessives
(``Nvidia's Blackwell`` vs ``Nvidia Blackwell``), a leading article, word
reordering, a dropped middle token — so a grounded paraphrase is never
flagged.  Being permissive here is deliberate: the consumers drop sentences
and block deliveries, and a false accusation is worse than a missed one.

*Honest hedges* — sentences carrying a hedge marker are exempt.  A product
that says a detail "is not disclosed in the available sources" is CORRECT
behaviour (#179/#191) and is never treated as an ungrounded claim.

Deliberately not in scope: number-claim verification, cross-product identity
claims, and URL reachability.  Those live in ``scripts/quality_gate.py``
(C6/H1/C5/X1) and in the prompt constraints; this module covers exactly the
"entity the sources never mentioned" class.
"""

from __future__ import annotations

import re
from typing import Iterable, Mapping

#: Honest-hedge markers (#179/#191): a sentence stating that the sources do
#: NOT provide a detail is correct behaviour, never an ungrounded claim.
HONEST_HEDGE_RE = re.compile(
    r"not (?:stated|disclosed|provided|specified|mentioned|reported|available)|"
    r"not in the (?:sources?|entries?)|no .{0,20} disclosed|undisclosed|"
    r"not detailed|could not be (?:found|determined|verified)",
    re.IGNORECASE,
)

# Uppercase ranges for the scripts a product realistically cites: Latin-1
# Supplement + Latin Extended-A (accented names such as ``Jalapeño`` — an
# ASCII-only class splits it into the meaningless ``Jalape`` plus a
# non-matching ``ñ``), Cyrillic, and Greek.
_UPPER = "A-Z\u00c0-\u00de\u0100-\u017f\u0400-\u042f\u0391-\u03a9"
_WORD = r"\w&.'\u2019-"

_MULTI_ENTITY_RE = re.compile(rf"\b[{_UPPER}][{_WORD}]*(?:\s+[{_UPPER}][{_WORD}]*){{0,5}}\b")
_TITLE_TOKEN_RE = re.compile(rf"\b[{_UPPER}][{_WORD}]+\b")

# URL / markdown-link spans: their path segments are capitalized by accident
# and are never entity claims.
_URL_RE = re.compile(r"https?://\S+")
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")

#: Capitalized nouns that are product chrome, calendar vocabulary, or a common
#: acronym — never entity names.  Kept in sync with ``scripts/quality_gate.py``'s
#: stoplist so the dev-side and delivery-side verdicts agree.
_GENERIC_ENTITY_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "the",
        "this",
        "that",
        "these",
        "those",
        "how",
        "what",
        "why",
        "when",
        "where",
        "which",
        "who",
        "weekly",
        "monthly",
        "daily",
        "digest",
        "report",
        "column",
        "tutorial",
        "presentation",
        "premium",
        "enterprise",
        "magazine",
        "briefing",
        "references",
        "reference",
        "source",
        "sources",
        "domain",
        "period",
        "generated",
        "total",
        "entries",
        "entry",
        "executive",
        "summary",
        "key",
        "findings",
        "recommendations",
        "implications",
        "risks",
        "action",
        "required",
        "metrics",
        "overview",
        "introduction",
        "conclusion",
        "appendix",
        "market",
        "trend",
        "trends",
        "news",
        "business",
        "analysis",
        "insight",
        "insights",
        "outlook",
        "week",
        "month",
        "year",
        "day",
        "date",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "english",
        "chinese",
        "french",
        "german",
        "spanish",
        "hindi",
        "italian",
        "korean",
        "portuguese",
        "russian",
        "japanese",
        "ai",
        "ml",
        "llm",
        "api",
        "apis",
        "url",
        "urls",
        "http",
        "https",
        "eur",
        "usd",
        "rmb",
        "cny",
        "gdp",
        "ipo",
        "ceo",
        "cto",
        "cfo",
        "saas",
        "paas",
        "faq",
        "sms",
        "email",
        "it",
        "hr",
        "nlp",
        "note",
        "notes",
        "ecommerce",
        "industry",
        "industries",
        "technology",
        "software",
        "hardware",
        "platform",
        "product",
        "products",
        "services",
        "service",
        "businesses",
        "tools",
        "tool",
        "startups",
        "startup",
        "company",
        "companies",
        "sectors",
        "sector",
        "apps",
        "app",
        "analysts",
        "observers",
        "experts",
        "researchers",
        "founders",
        "team",
        "teams",
        "investors",
        "customers",
        "consumer",
        "consumers",
        "supplier",
        "suppliers",
        "regulator",
        "regulators",
        "officials",
        "big",
        "idea",
        "issue",
        "issues",
        "topics",
        "readers",
        "reading",
        "language",
        "languages",
        "feature",
        "story",
        "editor",
        "read",
        "choose",
        "pick",
        "slide",
        "slides",
        "article",
        "articles",
        "item",
        "items",
        "point",
        "points",
        "takeaway",
        "takeaways",
        "finding",
        "checklist",
        "matrix",
        "scope",
        "selected",
        "edition",
        "speaker",
        "cadence",
        "collection",
        "inbox",
        "coverage",
        "topic",
        "topics",
        "n/a",
        "tbd",
        "none",
        "yes",
        "no",
        "not",
        "base",
        "data",
        "quality",
        "development",
        "clinical",
        "use",
        "used",
        "remove",
        "removed",
        "presence",
        "populate",
        "artificial",
        "gene",
        "knowledge",
    }
)

#: A sentence shorter than this carries no assertion worth checking; scanning
#: it produces only noise (company suffixes, units, list fragments).
_MIN_CLAIM_SENTENCE_CHARS = 40

#: Possessive markers stripped per token before the token-containment test.
_POSSESSIVE_RE = re.compile(r"['\u2019]s$")

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\u3002\uff01\uff1f])\s+|\n+")
_SENTENCE_END_RE = re.compile(r"[.!?\u3002\uff01\uff1f:;]\s*$")


def _content_tokens(phrase: str) -> tuple[str, ...]:
    """Return *phrase*'s case-folded content tokens, possessives stripped.

    ``"Nvidia's Blackwell"`` -> ``("nvidia", "blackwell")``.  Tokens listed in
    :data:`_GENERIC_ENTITY_STOP` and single-character tokens are dropped: they
    carry no discriminative signal and would otherwise make the containment
    test vacuous.
    """
    return tuple(
        token
        for word in phrase.split()
        if (token := _POSSESSIVE_RE.sub("", word.strip(".,;:()[]{}\"'").lower()))
        and len(token) > 1
        and token not in _GENERIC_ENTITY_STOP
    )


def _tokenize(text: str) -> frozenset[str]:
    """Case-folded token set of *text*, possessives stripped."""
    return frozenset(
        token
        for word in re.split(r"[^\w'\u2019-]+", text.lower())
        if (token := _POSSESSIVE_RE.sub("", word))
    )


def _strip_non_prose(text: str) -> str:
    """Blank out URL and markdown-link spans, preserving character offsets."""
    for pattern in (_URL_RE, _MD_LINK_RE):
        text = pattern.sub(lambda m: " " * len(m.group(0)), text)
    return text


#: A trailing run of pure markdown structure — list bullet, blockquote, or
#: bold/italic delimiters — reaching back to a line start. Title-Case after such
#: a run is sentence-initial, so it is capitalisation rather than an entity.
_MD_LEAD_NOISE_RE = re.compile(r"(?:\A|\n)[ \t>]*(?:[-*+][ \t]+|\d+[.)][ \t]+)?[*_`]*[ \t]*\Z")


def _is_sentence_initial(sentence: str, pos: int) -> bool:
    preceding = sentence[:pos].strip()
    return not preceding or bool(
        _SENTENCE_END_RE.search(preceding) or _MD_LEAD_NOISE_RE.search(preceding)
    )


def _single_token_claims(sentence: str) -> list[str]:
    """Single Title-Case tokens that are NOT sentence-initial."""
    claims: list[str] = []
    for match in _TITLE_TOKEN_RE.finditer(sentence):
        if _is_sentence_initial(sentence, match.start()):
            continue
        if match.group(0).lower() in _GENERIC_ENTITY_STOP:
            continue
        claims.append(match.group(0))
    return claims


def _entity_claims(text: str) -> list[str]:
    """Ordered, de-duplicated entity candidates in *text*.

    Multi-token Title-Case runs plus non-sentence-initial single Title-Case
    tokens (see the module docstring's candidate classes).  Candidates with no
    discriminative content token are dropped.
    """
    stripped = _strip_non_prose(text)
    seen: dict[str, None] = {}
    for match in _MULTI_ENTITY_RE.finditer(stripped):
        words = match.group(0).split()
        while words and words[0].lower() in _GENERIC_ENTITY_STOP:
            words.pop(0)
        if len(words) >= 2:
            seen.setdefault(" ".join(words), None)
    for token in _single_token_claims(stripped):
        seen.setdefault(token, None)
    return [candidate for candidate in seen if _content_tokens(candidate)]


def grounding_corpus(entries: Iterable[Mapping[str, object]]) -> str:
    """Build the grounding corpus from the supplied product entries.

    Concatenates each entry's ``title``, ``summary``, ``description``,
    ``content`` and ``tags`` — the material the synthesis was actually given
    (``description`` is the report-path reference shape's summary field).
    Callers MUST pass the entries handed to the model; a corpus built from
    anything else would make every verdict meaningless.
    """
    parts: list[str] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        for key in ("title", "summary", "description", "content", "tags"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value)
            elif isinstance(value, (list, tuple)):
                parts.extend(str(item) for item in value if str(item).strip())
    return "\n".join(parts)


def split_sentences(text: str) -> list[str]:
    """Split *text* into claim-sized sentences."""
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]


def _is_supported(candidate: str, corpus_lower: str, corpus_tokens: frozenset[str]) -> bool:
    if candidate.lower() in corpus_lower:
        return True
    tokens = _content_tokens(candidate)
    return bool(tokens) and all(token in corpus_tokens for token in tokens)


def ungrounded_entities(text: str, corpus: str) -> list[str]:
    """Return entity candidates in *text* that *corpus* does not support.

    An empty *corpus* yields no findings: there is nothing to ground against,
    so there is no verdict to hand down (the same "no corpus, no drift" rule
    ``scripts/quality_gate.py`` C6 applies).
    """
    if not corpus.strip():
        return []
    corpus_lower = corpus.lower()
    corpus_tokens = _tokenize(corpus)
    unsupported: dict[str, None] = {}
    for sentence in split_sentences(text):
        if len(sentence) < _MIN_CLAIM_SENTENCE_CHARS:
            continue
        if HONEST_HEDGE_RE.search(sentence):
            continue
        for candidate in _entity_claims(sentence):
            if _is_supported(candidate, corpus_lower, corpus_tokens):
                continue
            unsupported.setdefault(candidate, None)
    return list(unsupported)
