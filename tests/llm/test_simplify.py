"""Tests for simplify_text() — CEFR-level content simplification (E14).

All LLM calls are mocked — no real API calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from autoinfo.output import simplify_text, _VALID_SIMPLIFY_TARGETS


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def sample_text() -> str:
    """Return a short English paragraph for simplification testing."""
    return (
        "The integration of heterogeneous data sources requires robust "
        "ETL pipelines and sophisticated schema-mapping algorithms to ensure "
        "semantic consistency across the enterprise data warehouse."
    )


@pytest.fixture
def mock_litellm_simplify() -> MagicMock:
    """Return a mock litellm module that returns simplified text."""
    m = MagicMock()
    m.completion.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content="Connecting different data sources needs strong data pipelines."
                )
            )
        ]
    )
    return m


@pytest.fixture
def mock_classify_original() -> MagicMock:
    """Return results for classify_text that reports original as B2."""

    def _classify(text: str, lang: str = "en", model_config: dict | None = None) -> dict:  # noqa: ARG001
        return {"cefr_level": "B2", "confidence": 0.85}

    return MagicMock(side_effect=_classify)


@pytest.fixture
def mock_classify_simplified() -> MagicMock:
    """Return results for classify_text that reports simplified as A2."""

    def _classify(text: str, lang: str = "en", model_config: dict | None = None) -> dict:  # noqa: ARG001
        return {"cefr_level": "A2", "confidence": 0.85}

    return MagicMock(side_effect=_classify)


# ===================================================================
# Tests — success path
# ===================================================================


def test_simplify_success(
    sample_text: str,
    mock_litellm_simplify: MagicMock,
) -> None:
    """simplify_text returns verified=True when LLM produces valid simplification."""
    with patch(
        "litellm.completion", mock_litellm_simplify.completion
    ), patch(
        "autoinfo.cefr.classify_text",
        side_effect=[
            {"cefr_level": "B2", "confidence": 0.85},
            {"cefr_level": "A2", "confidence": 0.88},
        ],
    ):
        result = simplify_text(sample_text, "A2", "en")

    assert result["simplified"] == "Connecting different data sources needs strong data pipelines."
    assert result["original_level"] == "B2"
    assert result["simplified_level"] == "A2"
    assert result["verified"] is True
    assert "error" not in result


def test_simplify_verified_when_same_level(
    sample_text: str,
    mock_litellm_simplify: MagicMock,
) -> None:
    """verified=True even when simplified stays at same target level."""
    with patch(
        "litellm.completion", mock_litellm_simplify.completion
    ), patch(
        "autoinfo.cefr.classify_text",
        side_effect=[
            {"cefr_level": "B2", "confidence": 0.85},
            {"cefr_level": "B2", "confidence": 0.85},
        ],
    ):
        result = simplify_text(sample_text, "B2", "en")

    assert result["simplified_level"] == "B2"
    assert result["verified"] is True


def test_simplify_not_verified_when_higher(
    sample_text: str,
    mock_litellm_simplify: MagicMock,
) -> None:
    """verified=False when simplified level is higher than target."""
    with patch(
        "litellm.completion", mock_litellm_simplify.completion
    ), patch(
        "autoinfo.cefr.classify_text",
        side_effect=[
            {"cefr_level": "B1", "confidence": 0.85},  # original
            {"cefr_level": "C1", "confidence": 0.85},  # simplified is HIGHER than target A2
        ],
    ):
        result = simplify_text(sample_text, "A2", "en")

    assert result["simplified_level"] == "C1"
    assert result["verified"] is False


# ===================================================================
# Tests — invalid target_level
# ===================================================================


def test_simplify_invalid_level_A0(sample_text: str) -> None:
    """Call with invalid target_level returns error and unverified."""
    result = simplify_text(sample_text, "A0", "en")
    assert result["verified"] is False
    assert "error" in result
    assert "Invalid target_level" in result["error"]


def test_simplify_invalid_level_C2(sample_text: str) -> None:
    """C2 is not a valid target_level (only A1-C1)."""
    result = simplify_text(sample_text, "C2", "en")
    assert result["verified"] is False
    assert "error" in result
    assert "Invalid target_level" in result["error"]


def test_simplify_invalid_level_garbage(sample_text: str) -> None:
    """Non-CEFR level raises validation error."""
    result = simplify_text(sample_text, "beginner", "en")
    assert result["verified"] is False
    assert "error" in result


def test_simplify_empty_content() -> None:
    """Empty content returns error."""
    result = simplify_text("", "A1", "en")
    assert result["verified"] is False
    assert "error" in result
    assert result["simplified"] == ""


def test_simplify_whitespace_content() -> None:
    """Whitespace-only content returns error."""
    result = simplify_text("   \n  ", "A1", "en")
    assert result["verified"] is False
    assert "error" in result


def test_simplify_valid_levels(sample_text: str, mock_litellm_simplify: MagicMock) -> None:
    """All valid target levels pass validation without Invalid target_level error."""
    with patch("litellm.completion", mock_litellm_simplify.completion), \
         patch("autoinfo.cefr.classify_text", side_effect=[{"cefr_level": "B2", "confidence": 0.9}] * 10):
        for level in _VALID_SIMPLIFY_TARGETS:
            result = simplify_text(sample_text, level, "en")
            error = result.get("error", "")
            assert "Invalid target_level" not in error, f"Failed for level {level}"


# ===================================================================
# Tests — LLM failure path
# ===================================================================


def test_simplify_llm_exception(
    sample_text: str,
) -> None:
    """LLM exception returns original text with verified=False."""
    with patch("autoinfo.cefr.classify_text", return_value={"cefr_level": "C1", "confidence": 0.9}), \
         patch("litellm.completion", side_effect=RuntimeError("API unavailable")):

        result = simplify_text(sample_text, "A2", "en")

    assert result["simplified"] == sample_text  # original returned
    assert result["original_level"] == "C1"
    assert result["simplified_level"] == "unknown"
    assert result["verified"] is False
    assert "API unavailable" in result["error"]


def test_simplify_llm_empty_response(
    sample_text: str,
) -> None:
    """LLM returns empty string → fallback to original."""
    mock_lm = MagicMock()
    mock_lm.completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=""))]
    )

    with patch("litellm.completion", mock_lm.completion), \
         patch("autoinfo.cefr.classify_text", return_value={"cefr_level": "B1", "confidence": 0.8}):
        result = simplify_text(sample_text, "A2", "en")

    assert result["simplified"] == sample_text
    assert result["verified"] is False
    assert "empty response" in result["error"]




def test_simplify_language_zh(
    sample_text: str,
    mock_litellm_simplify: MagicMock,
) -> None:
    """Chinese language parameter is accepted."""
    with patch("litellm.completion", mock_litellm_simplify.completion), \
         patch(
            "autoinfo.cefr.classify_text",
            side_effect=[
                {"cefr_level": "B2", "confidence": 0.8},
                {"cefr_level": "A1", "confidence": 0.9},
            ],
         ):
        result = simplify_text(sample_text, "A1", "zh")

    assert result["verified"] is True
    assert result["original_level"] == "B2"
    assert result["simplified_level"] == "A1"


def test_simplify_language_ja(
    sample_text: str,
    mock_litellm_simplify: MagicMock,
) -> None:
    """Japanese language parameter is accepted."""
    with patch("litellm.completion", mock_litellm_simplify.completion), \
         patch(
            "autoinfo.cefr.classify_text",
            side_effect=[
                {"cefr_level": "B1", "confidence": 0.7},
                {"cefr_level": "A2", "confidence": 0.85},
            ],
         ):
        result = simplify_text(sample_text, "A2", "ja")

    assert result["verified"] is True
    assert result["simplified_level"] == "A2"
