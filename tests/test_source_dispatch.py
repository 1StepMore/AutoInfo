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

from pathlib import Path
from typing import Any

import yaml

from autoinfo.collect import _build_handler
from autoinfo.config import SourceConfig

DEMO_DIR = Path(__file__).resolve().parents[1] / "src" / "autoinfo" / "data" / "domains"

# All 5 demo domains
DOMAINS: list[str] = [
    "medical-research",
    "ai-commercial",
    "financial-intelligence",
    "tech-ai-developer",
    "language-learning",
]

# Expected dispatch results
# All sources now pass — HttpApiHandler handles any type=api source
# that isn't pubmed (which gets PubMedHandler).
EXPECTED_PASS: dict[str, list[str]] = {
    "medical-research": ["pubmed", "arXiv", "CrossRef"],
    "ai-commercial": ["techcrunch", "producthunt", "Crunchbase", "LMSYS"],
    "financial-intelligence": ["Alpha Vantage", "FRED", "SEC EDGAR", "Twelve Data", "World Bank Data"],
    "tech-ai-developer": ["Substack RSS (tech) — Pragmatic Engineer", "GitHub Trending", "HackerNews API", "Stack Exchange", "ProductHunt"],
    "language-learning": ["voa-learning-english", "project-gutenberg", "news-in-levels", "commonlit"],
}

EXPECTED_FAIL: dict[str, list[str]] = {
    "medical-research": [],
    "ai-commercial": [],
    "financial-intelligence": [],
    "tech-ai-developer": [],
    "language-learning": [],
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
    return data["sources"]


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
    assert not all_unexpected, (
        f"Unexpected exceptions ({len(all_unexpected)}):\n" +
        "\n".join(f"  {d}/{n}: {e}" for d, n, e in all_unexpected)
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

        # 3. Grand totals: 21 pass, 0 fail
        assert len(all_pass) == 21, f"Expected 21 PASS, got {len(all_pass)}"
        assert len(all_fail) == 0, f"Expected 0 FAIL, got {len(all_fail)}"
        assert total == 21, f"Expected 21 total sources, got {total}"
