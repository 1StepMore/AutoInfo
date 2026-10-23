"""Tests for source dispatch logic — verifies every configured demo source
has a corresponding handler.

This tests a different concern than ``test_demo_sources.py`` (which validates
YAML structure). Here we verify that the dispatch function ``_build_handler()``
in ``collect.py`` can actually process each source configuration.

Dispatch rules (from ``collect.py`` ``_build_handler()``):

1. ``type == "api"`` AND ``"pubmed" in name`` → PubMedHandler
2. ``type == "rss"`` → RSSHandler
3. ``type == "web"`` → WebHandler
4. ``type in ("email", "email_imap")`` → EmailHandler
5. ``type == "pdf"`` → PDFHandler
6. ``type == "api"`` (generic) → HttpApiHandler
7. Anything else → ValueError("Unknown source type...")
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
import yaml

from autoinfo.collect import _build_handler
from autoinfo.collectors.gdelt import GDELTHandler
from autoinfo.collectors.registry import (
    NON_BUILDABLE_SOURCE_TYPES,
    CollectorRegistration,
    register_collector,
    registered_source_types,
    registrations_for,
    unregister_collector,
)
from autoinfo.collectors.rss import RSSHandler
from autoinfo.collectors.unpaywall import UnpaywallHandler
from autoinfo.collectors.youtube import YouTubeHandler
from autoinfo.config import VALID_SOURCE_TYPES, SourceConfig

DEMO_DIR = Path(__file__).resolve().parents[2] / "src" / "autoinfo" / "data" / "domains"

# All 9 demo domains (5 legacy + 4 added by M3T24)
DOMAINS: list[str] = [
    "medical-research",
    "ai-commercial",
    "financial-intelligence",
    "tech-ai-developer",
    "language-learning",
    "general-news",
    "gaming",
    "b2b",
    "retail",
]

# Expected dispatch results
# All sources now pass — HttpApiHandler handles any type=api source
# that isn't pubmed (which gets PubMedHandler).
EXPECTED_PASS: dict[str, list[str]] = {
    "medical-research": [
        "pubmed",
        "arXiv",
        "CrossRef",
        "dblp",
        "openalex",
        "semantic-scholar",
        "uspto",
    ],
    "ai-commercial": ["techcrunch", "producthunt", "Crunchbase", "36kr"],
    "financial-intelligence": [
        "Alpha Vantage",
        "FRED",
        "Finnhub",
        "SEC EDGAR",
        "Twelve Data",
        "World Bank Data",
        "Quandl/Nasdaq Data Link",
        "CNBC Investing",
        "TheStreet",
        "MarketWatch Markets (DJ)",  # #6/#7 (2026-08-24): MW feed domain reachable
        "WSJ Markets",  # #101-fin (2026-08-30): frozen feed, disabled but dispatchable
    ],
    "tech-ai-developer": [
        "Substack RSS (tech) — Pragmatic Engineer",
        "GitHub Trending",
        "HackerNews API",
        "Stack Exchange",
        "ProductHunt",
        "Reddit",
        "Spotify AI Podcasts",
        "Bilibili (B站)",
        "HN Algolia API",  # #6/#7 (2026-08-24): reachable on mainland CN
        "GitHub Blog",  # #6/#7 (2026-08-24): reachable on mainland CN
        "hnrss",  # #27 (2026-08-25): card-verified feeds
        "ars-technica",  # #27
        "techcrunch-ai",  # #27
        "infoq-cn",  # #27
        "lobsters",  # #27
        "juejin",  # #27
        "qbitai",  # #27
    ],
    "language-learning": ["project-gutenberg", "news-in-levels", "commonlit"],
    # M3T24 demo domains (D12/D14/D15/D16) — all sources dispatch cleanly.
    # #6/#7 (2026-08-24): GFW-blocked/dead feeds disabled but still present and
    # dispatchable; verified-reachable replacements added.
    "general-news": [
        "gdelt",
        "guardian-open-platform",
        "google-news-rss",
        "nyt",
        "ap-api",
        "zhihu-daily",
        "mastodon",
        "bluesky",
        "wechat2rss",
        # #433: wechat2rss is disabled (its feed_id was a `<replace-me>`
        # placeholder returning 404); this slot now carries jiemian instead.
        "jiemian",
        "medium-user",
        "medium-publication",
        "medium-tag",
        "the-atlantic",
        "wired",
        "time-magazine",
        "france24",
        "npr-news",
        "ars-technica",
        "the-verge",
        "engadget",
        "spacenews",
        "people-cn-world",
        "cgtn-world",
        "sina-marquee",
    ],
    "gaming": [
        "ign-rss",
        "polygon-rss",
        "gamesindustry-biz",
        "gcores-rss",
        "yystv-via-google-news",
        "gamespot",
        "pc-gamer",
        "eurogamer",
        "rock-paper-shotgun",
        "gematsu",
    ],
    "b2b": [
        "a16z",
        "hackernews",
        "saastr",
        "b2b-news-network",
        "marTech",
        # #195: producthunt / techcrunch / crunchbase-news added to the b2b
        # demo config so required_sources has no config-layer gap (matches
        # README's B2B source list and end-user-matrix.yaml).
        "producthunt",
        "techcrunch",
        "crunchbase-news",
    ],
    "retail": [
        "retail-dive",
        "modern-retail",
        "ebrun-via-google-news",
        "shopify-news",
        "digiday",
        "retailwire",
    ],
}

EXPECTED_FAIL: dict[str, list[str]] = {
    "medical-research": [],
    "ai-commercial": [],
    "financial-intelligence": [],
    "tech-ai-developer": [],
    "language-learning": [],
    "general-news": [],
    "gaming": [],
    "b2b": [],
    "retail": [],
}

# Flattened expected names for quick membership checks
_ALL_EXPECTED_PASS: set[str] = {n for names in EXPECTED_PASS.values() for n in names}
_ALL_EXPECTED_FAIL: set[str] = {n for names in EXPECTED_FAIL.values() for n in names}
_ALL_EXPECTED: set[str] = _ALL_EXPECTED_PASS | _ALL_EXPECTED_FAIL


def _load_sources(domain: str) -> list[dict[str, Any]]:
    """Load source definitions from a demo domain's ``sources.yaml``."""
    path = DEMO_DIR / domain / "sources.yaml"
    with open(path) as fh:
        data = yaml.safe_load(fh)
    return list(data["sources"])


def test_source_dispatch_pass_fail() -> None:
    """Verify each configured source has a dispatch path (pass or documented ValueError).

    Asserts:
    * No unexpected exceptions (anything other than ValueError).
    * Pass and fail counts match EXPECTED_PASS / EXPECTED_FAIL per domain.
    """
    all_pass: list[tuple[str, str]] = []
    all_fail: list[tuple[str, str]] = []
    all_unexpected: list[tuple[str, str, str]] = []

    for domain in DOMAINS:
        sources = _load_sources(domain)
        for src in sources:
            name: str = src["name"]
            config = SourceConfig(
                name=name,
                type=src["type"],
                url=src.get("url", ""),
            )
            try:
                handler = _build_handler(config)
                assert handler is not None, f"Handler returned None for {domain}/{name}"
                all_pass.append((domain, name))
            except ValueError:
                all_fail.append((domain, name))
            except Exception as exc:
                all_unexpected.append((domain, name, str(exc)))

    # -----------------------------------------------------------------------
    # Summary output
    # -----------------------------------------------------------------------
    total = len(all_pass) + len(all_fail) + len(all_unexpected)
    print()
    print("=" * 70)
    print("  Source Dispatch Test Summary")
    print("=" * 70)
    print(f"  Total sources tested: {total}")
    print(f"  ✅ PASS (handler created):              {len(all_pass)}")
    print(f"  ❌ FAIL (ValueError — documented gap):  {len(all_fail)}")
    if all_unexpected:
        print(f"  💥 UNEXPECTED ERROR:                  {len(all_unexpected)}")
    print()

    for domain in DOMAINS:
        domain_pass = sorted(n for d, n in all_pass if d == domain)
        domain_fail = sorted(n for d, n in all_fail if d == domain)
        domain_unexp = [f"{n}: {e}" for d, n, e in all_unexpected if d == domain]
        print(f"  [{domain}]")
        for n in domain_pass:
            print(f"    ✅ {n}")
        for n in domain_fail:
            print(f"    ❌ {n}")
        for n in domain_unexp:
            print(f"    💥 {n}")
        print()

    # -----------------------------------------------------------------------
    # Assertions
    # -----------------------------------------------------------------------

    # 1. No unexpected exception types
    assert not all_unexpected, f"Unexpected exceptions ({len(all_unexpected)}):\n" + "\n".join(
        f"  {d}/{n}: {e}" for d, n, e in all_unexpected
    )

    # 2. Pass / fail counts per domain match expected
    for domain in DOMAINS:
        domain_pass_names: set[str] = {n for d, n in all_pass if d == domain}
        domain_fail_names: set[str] = {n for d, n in all_fail if d == domain}

        assert domain_pass_names == set(EXPECTED_PASS[domain]), (
            f"{domain}: PASS mismatch.\n"
            f"  Expected: {sorted(EXPECTED_PASS[domain])}\n"
            f"  Got:      {sorted(domain_pass_names)}"
        )
        assert domain_fail_names == set(EXPECTED_FAIL[domain]), (
            f"{domain}: FAIL mismatch.\n"
            f"  Expected: {sorted(EXPECTED_FAIL[domain])}\n"
            f"  Got:      {sorted(domain_fail_names)}"
        )

    # 3. Grand totals, asserted ONCE, after every domain's per-name contract
    #    above has been checked.
    #
    #    These used to sit INSIDE the `for domain in DOMAINS:` loop with
    #    hardcoded literals (90 / 0 / 90). Two defects followed:
    #      (a) The loop evaluated them on its FIRST iteration
    #          (medical-research), so a later domain raised before its own
    #          name-set assertion was reached. PR #433 tripped exactly this:
    #          the real signal (a general-news name-set mismatch) was masked
    #          and CI surfaced only "Expected 90 PASS, got 91".
    #      (b) The literals were a second hand-maintained copy of a count
    #          already fully determined by EXPECTED_PASS, so every source
    #          addition required remembering to bump them.
    #    The count is therefore DERIVED from DOMAINS x EXPECTED_PASS.
    #    `total` stays a separate assertion because all_pass/all_fail are
    #    LISTS: a duplicate source name within one domain collapses in the
    #    per-domain SET comparison but still shows up in `total`.
    #    `len(all_fail) == 0` stays a LITERAL on purpose — "no demo source may
    #    fail dispatch" is a policy, and deriving it would let a future author
    #    quiet a red dispatch by adding a name to EXPECTED_FAIL.
    expected_pass_total = sum(len(EXPECTED_PASS[d]) for d in DOMAINS)
    assert len(all_pass) == expected_pass_total, (
        f"Expected {expected_pass_total} PASS, got {len(all_pass)}"
    )
    assert len(all_fail) == 0, f"Expected 0 FAIL, got {len(all_fail)}"
    assert total == expected_pass_total, (
        f"Expected {expected_pass_total} total sources, got {total}"
    )


# ---------------------------------------------------------------------------
# VALID_SOURCE_TYPES parity with the collector registry
# ---------------------------------------------------------------------------
# The registry (``autoinfo.collectors.registry``) is now the single source of
# truth for "which source types can be built for pull collection".  Types that
# are accepted as configuration values but have no pull collector are listed
# explicitly by the registry itself (``NON_BUILDABLE_SOURCE_TYPES``) so a
# forgotten registration cannot hide behind a hand-maintained test allowlist.


def test_valid_source_types_parity_with_registry() -> None:
    """VALID_SOURCE_TYPES == registered types + documented non-buildable types.

    Catches single-place drift in either direction: registering a collector
    for a type that ``add_source`` rejects, or accepting a config type that
    silently lost its registration.
    """
    registered = registered_source_types()
    expected = registered | set(NON_BUILDABLE_SOURCE_TYPES)

    missing_from_config = registered - set(VALID_SOURCE_TYPES)
    assert not missing_from_config, (
        "Types registered in the collector registry but missing from "
        f"VALID_SOURCE_TYPES: {sorted(missing_from_config)}"
    )

    unclassified = set(VALID_SOURCE_TYPES) - expected
    assert not unclassified, (
        "VALID_SOURCE_TYPES contains types that are neither registered nor "
        "declared non-buildable in NON_BUILDABLE_SOURCE_TYPES: "
        f"{sorted(unclassified)}"
    )

    stale_non_buildable = set(NON_BUILDABLE_SOURCE_TYPES) - set(VALID_SOURCE_TYPES)
    assert not stale_non_buildable, (
        "NON_BUILDABLE_SOURCE_TYPES lists types outside VALID_SOURCE_TYPES: "
        f"{sorted(stale_non_buildable)}"
    )

    assert set(VALID_SOURCE_TYPES) == expected


def test_non_buildable_types_are_exactly_the_known_ones() -> None:
    """``webhook`` is push-only and ``core`` is forward-declared — nothing else."""
    assert set(NON_BUILDABLE_SOURCE_TYPES) == {"webhook", "core"}


def test_every_non_buildable_type_raises_value_error() -> None:
    """A config may carry these types, but pull collection cannot build them."""
    for stype in sorted(NON_BUILDABLE_SOURCE_TYPES):
        with pytest.raises(ValueError, match="Unknown source type"):
            _build_handler(SourceConfig(name=f"x-{stype}", type=stype, url="https://e.com"))


def test_every_registered_type_builds_a_collector() -> None:
    """Every registry entry produces a Collector with the uniform contract."""
    from autoinfo.collectors.base import Collector

    for stype in sorted(registered_source_types()):
        handler = _build_handler(
            SourceConfig(name=f"test-{stype}", type=stype, url="https://example.com/x")
        )
        assert isinstance(handler, Collector), f"{stype} did not build a Collector"
        assert callable(handler.fetch_items), f"{stype} has no fetch_items"


def test_registry_has_no_dangling_predicate_entries() -> None:
    """Predicate entries resolve to a wildcard fallback for their type."""
    for stype in sorted(registered_source_types()):
        entries = registrations_for(stype)
        assert entries, f"{stype} registered with zero entries"
        assert any(e.name_contains is None for e in entries), (
            f"{stype} has only name-predicate entries — a source whose name "
            "matches none of them would resolve to no collector"
        )


def test_new_collector_needs_one_class_and_one_registration() -> None:
    """Boundary: a new collector = one class + one registry registration.

    Nothing in ``collect.py`` changes.  This is the acceptance test for the
    registry refactor (#580): it fails if adding a collector ever requires
    touching a dispatch chain again.
    """
    from autoinfo.collectors.base import Collector, CollectorContext

    class _BoundaryCollector(Collector):
        def __init__(self, source_config: SourceConfig) -> None:
            self.source_config = source_config
            self.seen: CollectorContext | None = None

        def fetch_items(self, ctx: CollectorContext) -> list[Any]:
            self.seen = ctx
            return []

    registration = CollectorRegistration("__boundary__", _BoundaryCollector)
    register_collector(registration)
    try:
        handler = _build_handler(
            SourceConfig(name="boundary", type="__boundary__", url="https://example.com/x")
        )
        assert isinstance(handler, _BoundaryCollector)

        ctx = CollectorContext(
            topic="boundary-topic",
            keywords=["alpha"],
            limit=0,
            url="https://example.com/x",
            query="q",
        )
        assert handler.fetch_items(ctx) == []
        assert handler.seen is ctx
        assert handler.seen.limit == 0, "limit=0 must survive as an explicit empty request"
        assert handler.seen.topic == "boundary-topic"
    finally:
        unregister_collector(registration)

    assert "__boundary__" not in registered_source_types()


# ---------------------------------------------------------------------------
# fetch_depth threading through dispatch (todo 14 — Phase B content depth)
# ---------------------------------------------------------------------------
# A source with ``fetch_depth: fulltext`` must reach its handler carrying the
# value, so the fulltext collectors (unpaywall / rss / youtube / gdelt) can
# branch on it. Handlers that receive only a settings dict must see it inside
# their ``config``; RSS (which receives only ``source_name``) must expose it
# as a handler attribute. Sources WITHOUT an explicit ``fetch_depth`` keep the
# ``"abstract"`` default — backward compatible.


@pytest.mark.parametrize(
    "source, handler_cls, settings_key",
    [
        (
            SourceConfig(
                name="oa-fulltext",
                type="unpaywall",
                fetch_depth="fulltext",
                settings={"provider": "core"},
            ),
            UnpaywallHandler,
            "provider",
        ),
        (
            SourceConfig(
                name="yt-fulltext",
                type="youtube",
                fetch_depth="fulltext",
                settings={"query": "machine learning"},
            ),
            YouTubeHandler,
            "query",
        ),
        (
            SourceConfig(
                name="news-fulltext",
                type="gdelt",
                fetch_depth="fulltext",
                settings={"maxrecords": 50},
            ),
            GDELTHandler,
            "maxrecords",
        ),
    ],
)
def test_fetch_depth_reaches_settings_based_handlers(
    source: SourceConfig,
    handler_cls: type[Any],
    settings_key: str,
) -> None:
    """``fetch_depth: fulltext`` on the source is visible on the constructed
    settings-based handler (unpaywall / youtube / gdelt)."""
    handler = _build_handler(source)
    assert isinstance(handler, handler_cls)
    assert handler.config.get("fetch_depth") == "fulltext"
    # Original settings survive alongside the injected fetch_depth.
    assert handler.config.get(settings_key) is not None
    # The shared SourceConfig settings dict is never mutated.
    assert "fetch_depth" not in source.settings


def test_fetch_depth_reaches_rss_handler() -> None:
    """RSS (which receives only ``source_name``) still sees per-source
    ``fetch_depth`` on the constructed handler."""
    handler = _build_handler(
        SourceConfig(
            name="feed-fulltext",
            type="rss",
            url="https://example.com/rss",
            fetch_depth="fulltext",
        )
    )
    assert isinstance(handler, RSSHandler)
    assert handler.source_name == "feed-fulltext"
    assert handler.fetch_depth == "fulltext"


def test_fetch_depth_defaults_to_abstract_when_unset() -> None:
    """Sources without an explicit ``fetch_depth`` behave identically to
    today: the ``"abstract"`` default flows through the dispatch."""
    rss = _build_handler(SourceConfig(name="feed", type="rss", url="https://example.com/rss"))
    assert isinstance(rss, RSSHandler)
    assert rss.fetch_depth == "abstract"

    for source in (
        SourceConfig(name="oa", type="unpaywall"),
        SourceConfig(name="yt", type="youtube"),
        SourceConfig(name="news", type="gdelt"),
    ):
        handler = _build_handler(source)
        assert handler.config.get("fetch_depth") == "abstract"
        assert isinstance(handler, (UnpaywallHandler, YouTubeHandler, GDELTHandler))


def test_grand_totals_are_not_asserted_inside_the_domain_loop() -> None:
    """Grand totals are asserted ONCE, after every per-domain contract.

    Regression guard for the masking defect in PR #433: while the totals were
    nested, the loop short-circuited on its first iteration (medical-research),
    so a name-set mismatch in a LATER domain was never reported. The defect is
    CONTROL-FLOW, so this guard is structural: it parses this module and fails
    if an accumulator is COMPARED inside a loop over ``DOMAINS``.

    It keys on ``ast.Assert`` nodes rather than bare references on purpose. The
    loop body must legitimately *read* ``all_pass``/``all_fail`` -- that is how
    it splits them per domain -- so flagging any reference would fail on correct
    code. What must never appear inside the loop is a comparison.

    Both directions are asserted so the guard cannot pass vacuously:
    (1) every accumulator IS still compared by some assert, so deleting the
        totals does not satisfy (2) by simply removing them;
    (2) no accumulator is COMPARED inside a ``for ... in DOMAINS`` body.
    """
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    accumulators = {"all_pass", "all_fail", "total"}

    def _asserted_names(node: ast.AST) -> set[str]:
        return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and n.id in accumulators}

    compared: set[str] = set()
    offenders: list[str] = []
    for node in ast.walk(tree):
        is_domains_loop = (
            isinstance(node, ast.For)
            and isinstance(node.iter, ast.Name)
            and node.iter.id == "DOMAINS"
        )
        if is_domains_loop:
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Assert):
                    hit = _asserted_names(stmt.test) & accumulators
                    if hit:
                        offenders.append(
                            f"line {stmt.lineno}: assert compares {sorted(hit)} "
                            f"inside 'for ... in DOMAINS:'"
                        )
        if isinstance(node, ast.Assert):
            compared |= _asserted_names(node.test)

    assert compared == accumulators, (
        f"Grand totals no longer all asserted. Compared: {sorted(compared)}; "
        f"expected: {sorted(accumulators)}"
    )
    assert not offenders, (
        "Grand totals are asserted inside the per-domain loop again -- a mismatch "
        "in any domain after the first will be masked by the total assertion:\n"
        + "\n".join(f"  {o}" for o in offenders)
    )
