"""Tests for 36kr RSS source configuration in ai-commercial domain.

Verifies the YAML config parses correctly and that the 36kr source
entry has all required fields for the RSS handler.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

DEMO_DIR = Path(__file__).resolve().parents[2] / "src" / "autoinfo" / "data" / "domains"


def _load_sources() -> list[dict]:
    path = DEMO_DIR / "ai-commercial" / "sources.yaml"
    with open(path) as fh:
        data = yaml.safe_load(fh)
    return data["sources"]


def _find_source(name: str) -> dict | None:
    for src in _load_sources():
        if src.get("name") == name:
            return src
    return None


class Test36krSource:
    """Verify the 36kr RSS source is correctly configured."""

    def test_source_exists(self) -> None:
        """36kr source entry is present in ai-commercial sources.yaml."""
        src = _find_source("36kr")
        assert src is not None, "36kr source not found in ai-commercial sources.yaml"

    def test_required_fields(self) -> None:
        """All required SourceConfig fields are present."""
        src = _find_source("36kr")
        assert src is not None
        assert src["name"] == "36kr"
        assert src["type"] == "rss"
        assert src["url"] == "https://www.36kr.com/feed"
        assert src["quality_tier"] == 2
        assert isinstance(src["enabled"], bool) and src["enabled"] is True

    def test_settings_block(self) -> None:
        """Settings block contains feed_url and rate_limit_per_second."""
        src = _find_source("36kr")
        assert src is not None
        settings = src.get("settings", {})
        assert settings.get("feed_url") == "https://www.36kr.com/feed"
        assert settings.get("rate_limit_per_second") == 1

    def test_field_mapping(self) -> None:
        """Field mapping maps RSS fields to Item fields."""
        src = _find_source("36kr")
        assert src is not None
        fm = src.get("field_mapping", {})
        assert fm.get("id") == "id"
        assert fm.get("title") == "title"
        assert fm.get("content") == "content"
        assert fm.get("source_url") == "link"
        assert fm.get("published_date") == "updated"

    def test_topics(self) -> None:
        """Topics are correctly assigned."""
        src = _find_source("36kr")
        assert src is not None
        topics = src.get("topics", [])
        assert "Chinese tech" in topics
        assert "startup" in topics
        assert len(topics) == 2

    def test_url_parseable_as_rss(self) -> None:
        """URL is a well-formed HTTPS URL."""
        src = _find_source("36kr")
        assert src is not None
        url: str = src["url"]
        assert url.startswith("https://")
        assert "36kr.com" in url
        assert url.endswith("/feed")

    def test_source_count_includes_36kr(self) -> None:
        """ai-commercial domain has all expected sources including 36kr."""
        sources = _load_sources()
        names = [s["name"] for s in sources]
        expected = {"techcrunch", "producthunt", "Crunchbase", "36kr"}
        assert set(names) == expected, f"Expected {expected}, got {names}"
