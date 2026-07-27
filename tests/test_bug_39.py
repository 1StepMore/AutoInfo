"""Regression test for Bug #39: repeated --tag crashes with Typer TypeError.

Bug: ``flag()`` in ``cli/summaries.py`` declared ``tag`` without ``: list[str]``
type annotation, so Typer could not parse repeated ``--tag`` options correctly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

_SAMPLE_CONFIG = {
    "project": {"name": "Bug39 Test", "created_at": "2026-07-28"},
    "llm": {
        "provider": "openrouter",
        "model": "deepseek/deepseek-chat",
        "api_key": "test-key",
    },
    "domains": [],
}


class TestBug39RepeatedTag:
    """Verify that repeated ``--tag`` options are parsed as a list."""

    @patch("autoinfo.kb.KBStore")
    def test_repeated_tag_options_parsed_as_list(
        self, MockKBStore: MagicMock, cli_runner: Any, tmp_config_dir: Path
    ) -> None:
        """Two --tag values should arrive as a list, not crash."""
        mock_store = MagicMock()
        mock_store.flag_for_knowledge_base.return_value = {
            "flagged": True,
            "entry_id": "test-entry",
            "tags": ["foo", "bar"],
            "importance": 3,
        }
        MockKBStore.return_value = mock_store

        from autoinfo.cli import app

        with patch("autoinfo.cli.summaries.get_config_path", return_value=tmp_config_dir):
            result = cli_runner.invoke(
                app,
                [
                    "summaries", "flag",
                    "test-entry",
                    "--tag", "foo",
                    "--tag", "bar",
                ],
            )

        # If the bug is present, result.exit_code is 2 (Typer TypeError)
        # or stdout contains a TypeError traceback.
        assert result.exit_code == 0, (
            f"Expected exit code 0, got {result.exit_code}. "
            f"Stderr: {result.stderr!r}"
        )
        assert "Traceback" not in result.output, (
            f"Unexpected traceback in output: {result.output}"
        )
        assert "Flagged" in result.stdout
        assert "foo" in result.stdout
        assert "bar" in result.stdout

    @patch("autoinfo.kb.KBStore")
    def test_repeated_tag_json_output(
        self, MockKBStore: MagicMock, cli_runner: Any, tmp_config_dir: Path
    ) -> None:
        """Repeated --tag works with --json flag."""
        mock_store = MagicMock()
        mock_store.flag_for_knowledge_base.return_value = {
            "flagged": True,
            "entry_id": "test-entry",
            "tags": ["foo", "bar"],
            "importance": 3,
        }
        MockKBStore.return_value = mock_store

        from autoinfo.cli import app

        with patch("autoinfo.cli.summaries.get_config_path", return_value=tmp_config_dir):
            result = cli_runner.invoke(
                app,
                [
                    "summaries", "flag",
                    "test-entry",
                    "--tag", "foo",
                    "--tag", "bar",
                    "--json",
                ],
            )

        assert result.exit_code == 0, (
            f"Expected exit code 0, got {result.exit_code}. "
            f"Stderr: {result.stderr!r}"
        )
        data = json.loads(result.stdout)
        assert data["tags"] == ["foo", "bar"]

    @patch("autoinfo.kb.KBStore")
    def test_single_tag_still_works(
        self, MockKBStore: MagicMock, cli_runner: Any, tmp_config_dir: Path
    ) -> None:
        """Single --tag (no repeat) should still work after fix."""
        mock_store = MagicMock()
        mock_store.flag_for_knowledge_base.return_value = {
            "flagged": True,
            "entry_id": "test-entry",
            "tags": ["solo"],
            "importance": 3,
        }
        MockKBStore.return_value = mock_store

        from autoinfo.cli import app

        with patch("autoinfo.cli.summaries.get_config_path", return_value=tmp_config_dir):
            result = cli_runner.invoke(
                app,
                ["summaries", "flag", "test-entry", "--tag", "solo"],
            )

        assert result.exit_code == 0
        assert "Traceback" not in result.output


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temp project with a valid ``.autoinfo/config.yaml``."""
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as fh:
        yaml.dump(_SAMPLE_CONFIG, fh, default_flow_style=False)
    return config_path


@pytest.fixture
def cli_runner() -> Any:
    """Return a CliRunner instance."""
    from typer.testing import CliRunner

    return CliRunner()
