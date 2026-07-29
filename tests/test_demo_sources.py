"""Tests for demo domain source YAML config files.

Verifies that all 5 demo domains have their expected sources defined
with valid structure.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

DEMO_DIR = Path(__file__).resolve().parents[1] / "src" / "autoinfo" / "data" / "domains"

EXPECTED = {
    "medical-research": {
        "old": ["pubmed"],
        "new": ["arXiv", "CrossRef"],
    },
    "ai-commercial": {
        "old": ["techcrunch", "producthunt"],
        "new": ["Crunchbase", "LMSYS"],
    },
    "language-learning": {
        "old": ["voa-learning-english", "project-gutenberg"],
        "new": ["news-in-levels", "commonlit"],
    },
    "financial-intelligence": {
        "old": ["Alpha Vantage", "FRED"],
        "new": ["SEC EDGAR", "Twelve Data", "World Bank Data"],
    },
    "tech-ai-developer": {
        "old": ["GitHub Trending", "HackerNews API"],
        "new": ["Stack Exchange", "ProductHunt", "Substack RSS (tech) — Pragmatic Engineer"],
    },
}


def _load_sources(domain: str) -> list[dict]:
    path = DEMO_DIR / domain / "sources.yaml"
    with open(path) as fh:
        data = yaml.safe_load(fh)
    return data["sources"]


@pytest.mark.parametrize("domain, old, new", [
    ("medical-research", ["pubmed"], ["arXiv", "CrossRef"]),
    ("ai-commercial", ["techcrunch", "producthunt"], ["Crunchbase", "LMSYS"]),
    ("language-learning", ["voa-learning-english", "project-gutenberg"], ["news-in-levels", "commonlit"]),
    ("financial-intelligence", ["Alpha Vantage", "FRED"], ["SEC EDGAR", "Twelve Data", "World Bank Data"]),
    ("tech-ai-developer", ["GitHub Trending", "HackerNews API"], ["Stack Exchange", "ProductHunt", "Substack RSS (tech) — Pragmatic Engineer"]),
])
class TestDemoSources:
    def test_old_sources_preserved(self, domain: str, old: list[str], new: list[str]) -> None:
        sources = _load_sources(domain)
        names = [s["name"] for s in sources]
        for name in old:
            assert name in names, f"{domain}: expected existing source {name!r} to be preserved"

    def test_new_sources_added(self, domain: str, old: list[str], new: list[str]) -> None:
        sources = _load_sources(domain)
        names = [s["name"] for s in sources]
        for name in new:
            assert name in names, f"{domain}: expected new source {name!r} to be present"

    def test_required_fields(self, domain: str, old: list[str], new: list[str]) -> None:
        sources = _load_sources(domain)
        for src in sources:
            assert "name" in src
            assert "type" in src
            assert "url" in src
            assert "quality_tier" in src
            assert isinstance(src["quality_tier"], int)

    def test_total_count(self, domain: str, old: list[str], new: list[str]) -> None:
        sources = _load_sources(domain)
        expected_count = len(old) + len(new)
        assert len(sources) == expected_count, (
            f"{domain}: expected {expected_count} sources, got {len(sources)}"
        )
