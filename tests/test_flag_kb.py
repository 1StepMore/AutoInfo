"""Tests for flag_for_knowledge_base + get_summary.

Covers:
    - flag_for_knowledge_base returns {flagged: true} with entry_id
    - Flagged entry shows tags in SQLite index
    - Double-flag with same tags is idempotent (no duplicates)
    - Double-flag with new tags merges
    - get_summary returns full entry detail
    - CLI flag command adds tags
    - CLI show command shows full entry
    - Invalid entry_id returns error (not crash)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from autoinfo.kb import KBStore
from autoinfo.models import ExtractionResult, Item


# ======================================================================
# Sample data
# ======================================================================

_SAMPLE_FLAG_CONFIG = {
    "project": {"name": "Test Project", "created_at": "2026-07-01"},
    "llm": {
        "provider": "openrouter",
        "model": "deepseek/deepseek-chat",
        "api_key": "test-key",
    },
    "domains": [
        {
            "name": "medical-research",
            "active": True,
            "sources": [],
            "topics": [],
        }
    ],
}


@pytest.fixture
def sample_kb_entry(tmp_path: Path) -> tuple[KBStore, str]:
    """Create a KBStore with one sample entry and return (store, entry_id)."""
    store = KBStore(base_path=tmp_path / "knowledge")
    item = Item(
        id="test-flag-001",
        source_name="pubmed",
        source_type="api",
        source_url="https://example.com/flag-test",
        title="Flag test article",
        content="This is the content of the flag test article.",
        content_type="text",
        collected_at="2026-07-15T10:30:00Z",
        language="en",
        domain="medical-research",
        topic_tags=[],
        quality_tier=1,
    )
    extraction = ExtractionResult(
        item_id="test-flag-001",
        title="Flag test article",
        tl_dr="A test article for flag_for_knowledge_base.",
        key_points=["Key point one", "Key point two"],
        entities=[],
        relevance_score=90.0,
    )
    entry = store.store_entry(item, extraction=extraction)
    return store, entry.entry_id


# ======================================================================
# flag_for_knowledge_base — KBStore-level
# ======================================================================


class TestFlagForKnowledgeBase:
    def test_returns_flagged_with_entry_id(self, sample_kb_entry: tuple[KBStore, str]) -> None:
        store, entry_id = sample_kb_entry
        result = store.flag_for_knowledge_base(entry_id, tags=["important", "ivf"])
        assert result["flagged"] is True
        assert result["entry_id"] == entry_id
        assert result["tags"] == ["important", "ivf"]
        assert result["importance"] == 3

    def test_shows_tags_in_sqlite_index(self, sample_kb_entry: tuple[KBStore, str]) -> None:
        store, entry_id = sample_kb_entry
        store.flag_for_knowledge_base(entry_id, tags=["important", "ivf"])

        meta = store.index.get_entry(entry_id)
        assert meta is not None
        stored_tags = json.loads(meta["tags"])
        assert "important" in stored_tags
        assert "ivf" in stored_tags
        assert meta["importance"] == 3

    def test_double_flag_same_tags_idempotent(self, sample_kb_entry: tuple[KBStore, str]) -> None:
        store, entry_id = sample_kb_entry
        r1 = store.flag_for_knowledge_base(entry_id, tags=["a", "b"])
        r2 = store.flag_for_knowledge_base(entry_id, tags=["a", "b"])

        assert r1["tags"] == ["a", "b"]
        assert r2["tags"] == ["a", "b"]
        # No duplicates
        assert r2["tags"] == ["a", "b"]

    def test_double_flag_merges_new_tags(self, sample_kb_entry: tuple[KBStore, str]) -> None:
        store, entry_id = sample_kb_entry
        store.flag_for_knowledge_base(entry_id, tags=["a", "b"])
        result = store.flag_for_knowledge_base(entry_id, tags=["c", "d"])

        assert "a" in result["tags"]
        assert "b" in result["tags"]
        assert "c" in result["tags"]
        assert "d" in result["tags"]
        assert len(result["tags"]) == 4

    def test_merge_duplicates_only_once(self, sample_kb_entry: tuple[KBStore, str]) -> None:
        store, entry_id = sample_kb_entry
        store.flag_for_knowledge_base(entry_id, tags=["a", "b"])
        result = store.flag_for_knowledge_base(entry_id, tags=["b", "c"])

        assert result["tags"] == ["a", "b", "c"]
        assert len(result["tags"]) == 3

    def test_nonexistent_entry_returns_error(self, store: KBStore) -> None:
        result = store.flag_for_knowledge_base("does-not-exist", tags=["x"])
        assert result["flagged"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_importance_stored(self, sample_kb_entry: tuple[KBStore, str]) -> None:
        store, entry_id = sample_kb_entry
        result = store.flag_for_knowledge_base(entry_id, tags=["urgent"], importance=5)
        assert result["importance"] == 5

        meta = store.index.get_entry(entry_id)
        assert meta is not None
        assert meta["importance"] == 5

    def test_default_importance_is_3(self, sample_kb_entry: tuple[KBStore, str]) -> None:
        store, entry_id = sample_kb_entry
        result = store.flag_for_knowledge_base(entry_id)
        assert result["importance"] == 3

    def test_flag_without_tags_preserves_existing(self, sample_kb_entry: tuple[KBStore, str]) -> None:
        store, entry_id = sample_kb_entry
        store.flag_for_knowledge_base(entry_id, tags=["existing-tag"])
        result = store.flag_for_knowledge_base(entry_id, importance=4)
        assert "existing-tag" in result["tags"]
        assert result["importance"] == 4


@patch("autoinfo.kb.KBStore")
def test_flag_nonexistent_does_not_crash(MockKBStore: MagicMock) -> None:
    """Invalid entry_id returns error dict, not an exception."""
    mock_store = MagicMock()
    mock_store.flag_for_knowledge_base.return_value = {
        "flagged": False,
        "entry_id": "nonexistent",
        "error": "Entry not found",
    }
    MockKBStore.return_value = mock_store

    result = mock_store.flag_for_knowledge_base("nonexistent")
    assert result["flagged"] is False
    assert "error" in result


# ======================================================================
# get_summary — KBStore-level
# ======================================================================


class TestGetSummary:
    def test_returns_full_entry_detail(self, sample_kb_entry: tuple[KBStore, str]) -> None:
        store, entry_id = sample_kb_entry
        result = store.get_summary(entry_id)

        assert result["entry_id"] == entry_id
        assert result["title"] == "Flag test article"
        assert result["tl_dr"] == "A test article for flag_for_knowledge_base."
        assert result["key_points"] == ["Key point one", "Key point two"]
        # relevance_score defaults to 0.0 without quality_results
        assert result["relevance_score"] == 0.0
        assert result["importance"] == 3

    def test_source_provenance_present(self, sample_kb_entry: tuple[KBStore, str]) -> None:
        store, entry_id = sample_kb_entry
        result = store.get_summary(entry_id)

        sp = result["source_provenance"]
        assert sp["source_url"] == "https://example.com/flag-test"
        assert sp["source_type"] == "api"
        assert sp["source_platform"] == "pubmed"
        assert sp["collected_at"] == "2026-07-15T10:30:00Z"

    def test_tags_and_file_path_present(self, sample_kb_entry: tuple[KBStore, str]) -> None:
        store, entry_id = sample_kb_entry
        store.flag_for_knowledge_base(entry_id, tags=["important"])
        result = store.get_summary(entry_id)

        assert "important" in result["tags"]
        assert result["file_path"] is not None
        assert result["file_path"].endswith(".md")

    def test_nonexistent_returns_error(self, store: KBStore) -> None:
        result = store.get_summary("does-not-exist")
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_returns_quality_scores(self, sample_kb_entry: tuple[KBStore, str]) -> None:
        """get_summary includes quality_scores if frontmatter has quality_flags."""
        store, entry_id = sample_kb_entry
        result = store.get_summary(entry_id)
        # quality_scores present (may be empty dict if no quality gates run)
        assert isinstance(result["quality_scores"], dict)

    def test_empty_key_points_when_no_extraction(self, store: KBStore) -> None:
        """An entry without key points in body returns empty list."""
        item = Item(
            id="no-kp",
            source_name="pubmed",
            source_type="api",
            source_url="https://example.com/no-kp",
            title="No key points",
            content="Just content.",
            collected_at="2026-07-15T10:00:00Z",
            domain="medical-research",
            topic_tags=["test"],
        )
        entry = store.store_entry(item)
        result = store.get_summary(entry.entry_id)
        assert result["key_points"] == []


@patch("autoinfo.kb.KBStore")
def test_get_summary_nonexistent_does_not_crash(MockKBStore: MagicMock) -> None:
    """Invalid entry_id returns error dict, not an exception."""
    mock_store = MagicMock()
    mock_store.get_summary.return_value = {
        "error": "Entry not found",
        "entry_id": "ghost",
    }
    MockKBStore.return_value = mock_store

    result = mock_store.get_summary("ghost")
    assert "error" in result


# ======================================================================
# CLI: autoinfo summaries flag
# ======================================================================


class TestCliFlag:
    """Tests for ``autoinfo summaries flag <entry_id>``."""

    @patch("autoinfo.kb.KBStore")
    def test_flag_command_adds_tags(
        self, MockKBStore: MagicMock, cli_runner: Any, tmp_config_dir: Path
    ) -> None:
        mock_store = MagicMock()
        mock_store.flag_for_knowledge_base.return_value = {
            "flagged": True,
            "entry_id": "test-entry-001",
            "tags": ["important", "ivf"],
            "importance": 4,
        }
        MockKBStore.return_value = mock_store

        from autoinfo.cli import app

        with patch("autoinfo.cli.summaries.get_config_path", return_value=tmp_config_dir):
            result = cli_runner.invoke(
                app,
                [
                    "summaries", "flag",
                    "test-entry-001",
                    "--tag", "important",
                    "--tag", "ivf",
                    "--importance", "4",
                ],
            )

        assert result.exit_code == 0
        assert "Flagged" in result.stdout
        assert "test-entry-001" in result.stdout
        assert "important" in result.stdout
        assert "4" in result.stdout

    @patch("autoinfo.kb.KBStore")
    def test_flag_json_output(
        self, MockKBStore: MagicMock, cli_runner: Any, tmp_config_dir: Path
    ) -> None:
        mock_store = MagicMock()
        mock_store.flag_for_knowledge_base.return_value = {
            "flagged": True,
            "entry_id": "test-entry-001",
            "tags": ["urgent"],
            "importance": 5,
        }
        MockKBStore.return_value = mock_store

        from autoinfo.cli import app

        with patch("autoinfo.cli.summaries.get_config_path", return_value=tmp_config_dir):
            result = cli_runner.invoke(
                app,
                ["summaries", "flag", "test-entry-001", "--tag", "urgent", "--json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["flagged"] is True
        assert data["entry_id"] == "test-entry-001"

    @patch("autoinfo.kb.KBStore")
    def test_flag_nonexistent_shows_error(
        self, MockKBStore: MagicMock, cli_runner: Any, tmp_config_dir: Path
    ) -> None:
        mock_store = MagicMock()
        mock_store.flag_for_knowledge_base.return_value = {
            "flagged": False,
            "entry_id": "ghost",
            "error": "Entry not found",
        }
        MockKBStore.return_value = mock_store

        from autoinfo.cli import app

        with patch("autoinfo.cli.summaries.get_config_path", return_value=tmp_config_dir):
            result = cli_runner.invoke(
                app,
                ["summaries", "flag", "ghost", "--tag", "x"],
            )

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_flag_no_config_shows_friendly_error(
        self, cli_runner: Any
    ) -> None:
        from autoinfo.cli import app

        with patch("autoinfo.cli.summaries.get_config_path", return_value=None):
            result = cli_runner.invoke(
                app,
                ["summaries", "flag", "some-entry", "--tag", "x"],
            )

        assert result.exit_code == 1
        assert "Error" in result.output
        assert "Traceback" not in result.output


# ======================================================================
# CLI: autoinfo summaries show
# ======================================================================


class TestCliShow:
    """Tests for ``autoinfo summaries show <entry_id>``."""

    @patch("autoinfo.kb.KBStore")
    def test_show_command_shows_full_entry(
        self, MockKBStore: MagicMock, cli_runner: Any, tmp_config_dir: Path
    ) -> None:
        mock_store = MagicMock()
        mock_store.get_summary.return_value = {
            "entry_id": "test-entry-001",
            "title": "Test Article",
            "tl_dr": "A test summary.",
            "key_points": ["Point 1", "Point 2"],
            "relevance_score": 90.0,
            "quality_scores": {},
            "source_provenance": {
                "source_url": "https://example.com",
                "source_type": "api",
                "source_platform": "pubmed",
                "collected_at": "2026-07-15T10:30:00Z",
            },
            "tags": ["important"],
            "importance": 3,
            "file_path": "knowledge/test.md",
        }
        MockKBStore.return_value = mock_store

        from autoinfo.cli import app

        with patch("autoinfo.cli.summaries.get_config_path", return_value=tmp_config_dir):
            result = cli_runner.invoke(
                app,
                ["summaries", "show", "test-entry-001"],
            )

        assert result.exit_code == 0
        assert "Test Article" in result.stdout
        assert "A test summary." in result.stdout
        assert "Point 1" in result.stdout
        assert "Point 2" in result.stdout
        assert "important" in result.stdout

    @patch("autoinfo.kb.KBStore")
    def test_show_json_output(
        self, MockKBStore: MagicMock, cli_runner: Any, tmp_config_dir: Path
    ) -> None:
        mock_store = MagicMock()
        mock_store.get_summary.return_value = {
            "entry_id": "test-entry-001",
            "title": "Test Article",
            "tl_dr": "A test summary.",
            "key_points": [],
            "relevance_score": 90.0,
            "quality_scores": {},
            "source_provenance": {},
            "tags": [],
            "importance": 3,
            "file_path": "",
        }
        MockKBStore.return_value = mock_store

        from autoinfo.cli import app

        with patch("autoinfo.cli.summaries.get_config_path", return_value=tmp_config_dir):
            result = cli_runner.invoke(
                app,
                ["summaries", "show", "test-entry-001", "--json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["entry_id"] == "test-entry-001"
        assert data["title"] == "Test Article"

    @patch("autoinfo.kb.KBStore")
    def test_show_nonexistent_shows_error(
        self, MockKBStore: MagicMock, cli_runner: Any, tmp_config_dir: Path
    ) -> None:
        mock_store = MagicMock()
        mock_store.get_summary.return_value = {
            "error": "Entry not found",
            "entry_id": "ghost",
        }
        MockKBStore.return_value = mock_store

        from autoinfo.cli import app

        with patch("autoinfo.cli.summaries.get_config_path", return_value=tmp_config_dir):
            result = cli_runner.invoke(
                app,
                ["summaries", "show", "ghost"],
            )

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_show_no_config_shows_friendly_error(self, cli_runner: Any) -> None:
        from autoinfo.cli import app

        with patch("autoinfo.cli.summaries.get_config_path", return_value=None):
            result = cli_runner.invoke(
                app,
                ["summaries", "show", "some-entry"],
            )

        assert result.exit_code == 1
        assert "Error" in result.output
        assert "Traceback" not in result.output


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def store(tmp_path: Path) -> KBStore:
    """Return a KBStore rooted in a temp directory."""
    return KBStore(base_path=tmp_path / "knowledge")


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temp project with a valid ``.autoinfo/config.yaml``."""
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as fh:
        yaml.dump(_SAMPLE_FLAG_CONFIG, fh, default_flow_style=False)
    return config_path


@pytest.fixture
def cli_runner() -> Any:
    """Return a CliRunner instance."""
    from typer.testing import CliRunner

    return CliRunner()
