"""Tests for the end-user ``content_preference`` output gate (B-001).

Verifies that ``generate_digest`` and ``generate_report`` filter KB
entries by tier according to the stored ``content_preference``:

- ``raw_only`` -> only 01-Raw entries feed the output
- ``processed_only`` -> only 02-Draft + 03-Wiki entries feed the output
- ``both`` / unset -> all tiers unchanged (backward compatible)
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

_RAW_ENTRY: dict[str, Any] = {
    "entry_id": "raw-001",
    "title": "Raw tier article one",
    "domain": "test-domain",
    "tier": "01-Raw",
    "source_url": "https://example.com/raw-001",
    "source_type": "rss",
    "source_platform": "demo",
    "collected_at": (date.today() - timedelta(days=1)).isoformat(),
    "summary": "Collected but not yet processed.",
    "tags": "[]",
    "quality_tier": 1,
    "relevance_score": 80.0,
    "dedup_status": "unique",
    "file_path": "",
}

_DRAFT_ENTRY: dict[str, Any] = {
    "entry_id": "draft-001",
    "title": "Draft tier article one",
    "domain": "test-domain",
    "tier": "02-Draft",
    "source_url": "https://example.com/draft-001",
    "source_type": "rss",
    "source_platform": "demo",
    "collected_at": (date.today() - timedelta(days=1)).isoformat(),
    "summary": "Agent processed, awaiting human promotion.",
    "tags": "[]",
    "quality_tier": 2,
    "relevance_score": 90.0,
    "dedup_status": "unique",
    "file_path": "",
}

_WIKI_ENTRY: dict[str, Any] = {
    "entry_id": "wiki-001",
    "title": "Wiki tier article one",
    "domain": "test-domain",
    "tier": "03-Wiki",
    "source_url": "https://example.com/wiki-001",
    "source_type": "rss",
    "source_platform": "demo",
    "collected_at": (date.today() - timedelta(days=1)).isoformat(),
    "summary": "Human promoted, append-only.",
    "tags": "[]",
    "quality_tier": 3,
    "relevance_score": 95.0,
    "dedup_status": "unique",
    "file_path": "",
}

_ALL_ENTRIES: list[dict[str, Any]] = [_RAW_ENTRY, _DRAFT_ENTRY, _WIKI_ENTRY]


def _prefs_result(preferences: dict[str, Any]) -> dict[str, Any]:
    """Shape returned by ``autoinfo.user_store.get_preferences``."""
    return {"user_id": "u-1", "preferences": preferences}


def _get_llm_extractor_class():
    """Return the LLMExtractor class for mocking."""
    from autoinfo.llm import LLMExtractor

    return LLMExtractor


# ---------------------------------------------------------------------------
# generate_digest gate
# ---------------------------------------------------------------------------


class TestDigestContentPreference:
    """``generate_digest`` filters entries by stored content_preference."""

    def _call_digest(
        self, preferences: dict[str, Any], user_id: str = "u-1"
    ) -> str:
        from autoinfo.output import generate_digest

        with (
            patch("autoinfo.output.KBStore") as mock_kb_cls,
            patch("autoinfo.output._call_llm_for_digest") as mock_llm,
            patch("autoinfo.user_store.get_preferences") as mock_prefs,
        ):
            mock_llm.return_value = {"executive_summary": "Synthesis."}
            mock_store = MagicMock()
            mock_store.list_entries.return_value = _ALL_ENTRIES
            mock_kb_cls.return_value = mock_store
            mock_prefs.return_value = _prefs_result(preferences)
            return generate_digest(
                domain="test-domain", period="weekly", user_id=user_id
            )

    def test_raw_only_excludes_processed_tiers(self) -> None:
        result = self._call_digest({"content_preference": "raw_only"})
        assert "Raw tier article one" in result
        assert "Draft tier article one" not in result
        assert "Wiki tier article one" not in result

    def test_processed_only_excludes_raw_tier(self) -> None:
        result = self._call_digest({"content_preference": "processed_only"})
        assert "Raw tier article one" not in result
        assert "Draft tier article one" in result
        assert "Wiki tier article one" in result

    def test_both_includes_all_tiers(self) -> None:
        result = self._call_digest({"content_preference": "both"})
        assert "Raw tier article one" in result
        assert "Draft tier article one" in result
        assert "Wiki tier article one" in result

    def test_default_both_when_unset(self) -> None:
        result = self._call_digest({})
        assert "Raw tier article one" in result
        assert "Draft tier article one" in result
        assert "Wiki tier article one" in result

    def test_no_user_id_unchanged(self) -> None:
        """No user_id means no preference lookup, all tiers included."""
        from autoinfo.output import generate_digest

        with (
            patch("autoinfo.output.KBStore") as mock_kb_cls,
            patch("autoinfo.output._call_llm_for_digest") as mock_llm,
        ):
            mock_llm.return_value = {"executive_summary": "Synthesis."}
            mock_store = MagicMock()
            mock_store.list_entries.return_value = _ALL_ENTRIES
            mock_kb_cls.return_value = mock_store
            result = generate_digest(domain="test-domain", period="weekly")

        assert "Raw tier article one" in result
        assert "Draft tier article one" in result
        assert "Wiki tier article one" in result


# ---------------------------------------------------------------------------
# generate_report gate
# ---------------------------------------------------------------------------


class TestReportContentPreference:
    """``generate_report`` filters entries by stored content_preference."""

    def _call_report(
        self, preferences: dict[str, Any], user_id: str = "u-1"
    ) -> str:
        from autoinfo.output import generate_report

        with (
            patch("autoinfo.output.KBStore") as mock_kb_cls,
            patch.object(
                _get_llm_extractor_class(),
                "extract",
                side_effect=RuntimeError("llm unavailable"),
            ),
            patch("autoinfo.user_store.get_preferences") as mock_prefs,
        ):
            mock_store = MagicMock()
            mock_store.list_entries.return_value = _ALL_ENTRIES
            mock_kb_cls.return_value = mock_store
            mock_prefs.return_value = _prefs_result(preferences)
            return generate_report(
                domain="test-domain", format="markdown", user_id=user_id
            )

    def test_raw_only_excludes_processed_tiers(self) -> None:
        result = self._call_report({"content_preference": "raw_only"})
        assert "Raw tier article one" in result
        assert "Draft tier article one" not in result
        assert "Wiki tier article one" not in result

    def test_processed_only_excludes_raw_tier(self) -> None:
        result = self._call_report({"content_preference": "processed_only"})
        assert "Raw tier article one" not in result
        assert "Draft tier article one" in result
        assert "Wiki tier article one" in result

    def test_both_includes_all_tiers(self) -> None:
        result = self._call_report({"content_preference": "both"})
        assert "Raw tier article one" in result
        assert "Draft tier article one" in result
        assert "Wiki tier article one" in result

    def test_default_both_when_unset(self) -> None:
        result = self._call_report({})
        assert "Raw tier article one" in result
        assert "Draft tier article one" in result
        assert "Wiki tier article one" in result

    def test_no_user_id_unchanged(self) -> None:
        """No user_id means no preference lookup, all tiers included."""
        from autoinfo.output import generate_report

        with (
            patch("autoinfo.output.KBStore") as mock_kb_cls,
            patch.object(
                _get_llm_extractor_class(),
                "extract",
                side_effect=RuntimeError("llm unavailable"),
            ),
        ):
            mock_store = MagicMock()
            mock_store.list_entries.return_value = _ALL_ENTRIES
            mock_kb_cls.return_value = mock_store
            result = generate_report(domain="test-domain", format="markdown")

        assert "Raw tier article one" in result
        assert "Draft tier article one" in result
        assert "Wiki tier article one" in result
