"""Tests for LLM-based translation (localize_content).

Covers:
- Direct content mode: translates raw text without storage
- Content-ID mode: reads from KB entry, translates, stores file
- Missing content_id/content raises ValueError
- Empty target_lang raises ValueError
- Missing source_lang in direct mode raises ValueError
- LLM failure / empty response handling
- MCP _handle_localize_content handler
- CLI translate command
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.output import localize_content


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_SAMPLE_MD = """---
title: Improved IVF outcomes with time-lapse embryo imaging
entry_id: med-ivf-001
domain: medical-research
tier: 01-Raw
tags: ["IVF", "embryo imaging"]
language: en
---

Time-lapse embryo imaging has been proposed as a non-invasive method
to improve embryo selection in IVF cycles. We conducted a multicenter
randomized controlled trial involving 1,200 patients.

The live birth rate was significantly higher in the time-lapse group
compared to the control group (48.2% vs. 39.5%, p=0.006).
"""

_KB_ENTRY = {
    "entry_id": "med-ivf-001",
    "title": "Improved IVF outcomes with time-lapse embryo imaging",
    "domain": "medical-research",
    "tier": "01-Raw",
    "source_url": "https://example.com/ivf-001",
    "source_type": "api",
    "source_platform": "pubmed",
    "collected_at": "2026-07-15T10:30:00Z",
    "summary": "Time-lapse imaging improves live birth rates.",
    "tags": ["IVF", "embryo imaging"],
    "language": "en",
    "quality_tier": 1,
    "relevance_score": 92.0,
    "dedup_status": "unique",
    "file_path": "/fake/path/med-ivf-001.md",
}

_MOCK_TRANSLATION = {
    "translated_title": "时差胚胎成像改善IVF结局：一项随机对照试验",
    "translated_body": (
        "时差胚胎成像作为一种非侵入性方法，已被提出用于改善IVF周期中的胚胎选择。"
        "我们进行了一项多中心随机对照试验，纳入1,200名患者。\n\n"
        "时差组的活产率显著高于对照组（48.2% vs. 39.5%，p=0.006）。"
    ),
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def kb_md_file(tmp_path: Path) -> Path:
    """Create a temporary KB Markdown file matching _SAMPLE_MD."""
    fp = tmp_path / "med-ivf-001.md"
    fp.write_text(_SAMPLE_MD, encoding="utf-8")
    return fp


@pytest.fixture
def kb_entry_with_file(kb_md_file: Path) -> dict[str, Any]:
    """Return a KB entry dict with a real file_path."""
    entry = dict(_KB_ENTRY)
    entry["file_path"] = str(kb_md_file)
    return entry


# ---------------------------------------------------------------------------
# Direct content mode
# ---------------------------------------------------------------------------


@patch("autoinfo.output._call_llm_for_translation")
def test_localize_content_direct(mock_translate: MagicMock) -> None:
    """Direct content mode translates raw text and returns translated body."""
    mock_translate.return_value = _MOCK_TRANSLATION

    result = localize_content(
        content="Hello world, this is an IVF study.",
        source_lang="en",
        target_lang="zh",
    )

    assert result["success"] is True
    assert result["translated_body"] == _MOCK_TRANSLATION["translated_body"]
    assert result["target_lang"] == "zh"
    assert result["source_lang"] == "en"
    assert "file_path" not in result


@patch("autoinfo.output._call_llm_for_translation")
def test_localize_content_direct_missing_source_lang(
    mock_translate: MagicMock,
) -> None:
    """Direct content mode without source_lang raises ValueError."""
    with pytest.raises(ValueError, match="source_lang is required"):
        localize_content(content="Hello", target_lang="zh")


# ---------------------------------------------------------------------------
# Content-ID mode
# ---------------------------------------------------------------------------


@patch("autoinfo.output._call_llm_for_translation")
def test_localize_content_from_kb(
    mock_translate: MagicMock,
    kb_entry_with_file: dict[str, Any],
    tmp_path: Path,
) -> None:
    """Content-ID mode translates KB entry and writes translated file."""
    mock_translate.return_value = _MOCK_TRANSLATION

    with patch("autoinfo.kb.KBStore") as MockKBStore:
        store_instance = MagicMock()
        store_instance.get_entry.return_value = kb_entry_with_file
        MockKBStore.return_value = store_instance

        result = localize_content(
            content_id="med-ivf-001",
            target_lang="zh",
        )

    assert result["success"] is True
    assert result["translated_title"] == _MOCK_TRANSLATION["translated_title"]
    assert result["translated_body"] == _MOCK_TRANSLATION["translated_body"]
    assert result["target_lang"] == "zh"
    assert result["source_lang"] == "en"
    assert result["content_id"] == "med-ivf-001"
    assert "file_path" in result

    if result["file_path"]:
        fp = Path(result["file_path"])
        assert fp.exists()
        content_text = fp.read_text(encoding="utf-8")
        assert "translated_from" in content_text
        assert _MOCK_TRANSLATION["translated_title"] in content_text


@patch("autoinfo.output._call_llm_for_translation")
def test_localize_content_from_kb_not_found(
    mock_translate: MagicMock,
) -> None:
    """Content-ID mode with non-existent entry raises ValueError."""
    with patch("autoinfo.kb.KBStore") as MockKBStore:
        store_instance = MagicMock()
        store_instance.get_entry.return_value = None
        MockKBStore.return_value = store_instance

        with pytest.raises(ValueError, match="not found"):
            localize_content(content_id="nonexistent", target_lang="zh")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_localize_content_no_params() -> None:
    """Calling with neither content_id nor content raises ValueError."""
    with pytest.raises(ValueError, match="Either content_id or content"):
        localize_content(target_lang="zh")


def test_localize_content_empty_target_lang() -> None:
    """Empty target_lang raises ValueError."""
    with pytest.raises(ValueError, match="target_lang is required"):
        localize_content(content="Hello", source_lang="en", target_lang="")


# ---------------------------------------------------------------------------
# LLM failure handling
# ---------------------------------------------------------------------------


@patch("autoinfo.output._call_llm_for_translation")
def test_localize_content_llm_failure(mock_translate: MagicMock) -> None:
    """When LLM call fails (returns empty), returns success=False."""
    mock_translate.return_value = {"translated_title": "", "translated_body": ""}

    result = localize_content(
        content="Hello world",
        source_lang="en",
        target_lang="zh",
    )

    assert result["success"] is False
    assert "error" in result


@patch("autoinfo.output._call_llm_for_translation")
def test_localize_content_empty_response(mock_translate: MagicMock) -> None:
    """When LLM returns empty translated_body, returns success=False."""
    mock_translate.return_value = {"translated_title": "", "translated_body": ""}

    result = localize_content(
        content="Hello world",
        source_lang="en",
        target_lang="zh",
    )

    assert result["success"] is False


# ---------------------------------------------------------------------------
# MCP handler
# ---------------------------------------------------------------------------


def test_mcp_handle_localize_content() -> None:
    """MCP _handle_localize_content dispatches to localize_content."""
    from autoinfo.mcp.server import _handle_localize_content

    with patch("autoinfo.output.localize_content") as mock_localize:
        mock_localize.return_value = {
            "success": True,
            "translated_body": "测试",
            "target_lang": "zh",
        }

        result = _handle_localize_content(
            content="Test", source_lang="en", target_lang="zh"
        )

        mock_localize.assert_called_once_with(
            content="Test", source_lang="en", target_lang="zh"
        )
        assert result["success"] is True
        assert result["translated_body"] == "测试"


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


def test_cli_translate_direct() -> None:
    """CLI `autoinfo output translate` with direct content works."""
    from autoinfo.cli.output import app
    from typer.testing import CliRunner

    runner = CliRunner()

    with patch("autoinfo.output.localize_content") as mock_localize:
        mock_localize.return_value = {
            "success": True,
            "translated_body": "测试内容",
            "source_lang": "en",
            "target_lang": "zh",
        }

        result = runner.invoke(
            app,
            [
                "translate",
                "--content",
                "Test content",
                "--source-lang",
                "en",
                "--target-lang",
                "zh",
            ],
        )

        assert result.exit_code == 0
        assert "Translation successful" in result.stdout


def test_cli_translate_content_id() -> None:
    """CLI `autoinfo output translate --content-id` works."""
    from autoinfo.cli.output import app
    from typer.testing import CliRunner

    runner = CliRunner()

    with patch("autoinfo.output.localize_content") as mock_localize:
        mock_localize.return_value = {
            "success": True,
            "translated_title": "测试标题",
            "translated_body": "测试内容",
            "file_path": "/tmp/test.md",
            "source_lang": "en",
            "target_lang": "zh",
        }

        result = runner.invoke(
            app,
            ["translate", "--content-id", "med-ivf-001", "--target-lang", "zh"],
        )

        assert result.exit_code == 0
        assert "Translation successful" in result.stdout
        assert "测试标题" in result.stdout
        assert "/tmp/test.md" in result.stdout


def test_cli_translate_failure() -> None:
    """CLI reports errors when translation fails."""
    from autoinfo.cli.output import app
    from typer.testing import CliRunner

    runner = CliRunner()

    with patch("autoinfo.output.localize_content") as mock_localize:
        mock_localize.return_value = {
            "success": False,
            "error": "LLM translation returned empty result",
        }

        result = runner.invoke(
            app,
            [
                "translate",
                "--content",
                "Test",
                "--source-lang",
                "en",
                "--target-lang",
                "zh",
            ],
        )

        assert result.exit_code == 1
        assert "Translation failed" in result.stderr
