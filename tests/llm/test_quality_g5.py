"""Tests for G5 translation accuracy gate.

Covers:
    - G5TranslationAccuracy.check() with faithful translation
    - G5TranslationAccuracy.check() with unfaithful translation
    - G5TranslationAccuracy.check() with malformed LLM response
    - G5TranslationAccuracy.check() with empty translation (skip)
    - G5TranslationAccuracy.check() when litellm is unavailable
    - G5 result stored in KB frontmatter via run_processing (--check-translation)
    - Without --check-translation, G5 is skipped
    - G5 failure doesn't block the pipeline
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.kb import KBStore, _build_frontmatter
from autoinfo.llm import LLMExtractor
from autoinfo.models import ExtractionResult, Item, KBEntry
from autoinfo.process import run_processing
from autoinfo.quality import (
    G5TranslationAccuracy,
    QualityResult,
)


# ===================================================================
# Helpers
# ===================================================================


def _mock_litellm(return_json: dict) -> MagicMock:
    """Build a mock ``litellm`` module whose ``completion()`` returns *return_json*."""
    mock_litellm = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(return_json)
    mock_litellm.completion.return_value = mock_response
    return mock_litellm


def _mock_litellm_raw(raw_text: str) -> MagicMock:
    """Build a mock ``litellm`` module whose ``completion()`` returns raw text."""
    mock_litellm = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = raw_text
    mock_litellm.completion.return_value = mock_response
    return mock_litellm


def _make_quality_results_base() -> dict[str, QualityResult]:
    """Return quality gate results with G1-G3 all passing."""
    return {
        "G1-SourceAuthority": QualityResult(
            gate_name="G1-SourceAuthority",
            passed=True,
            score=1.0,
            details={"quality_tier": 1, "source_name": "pubmed"},
        ),
        "G2-Dedup": QualityResult(
            gate_name="G2-Dedup",
            passed=True,
            score=1.0,
            details={"is_duplicate": False, "matched_by": None},
        ),
        "G3-RelevanceScoring": QualityResult(
            gate_name="G3-RelevanceScoring",
            passed=True,
            score=85.0,
            details={"hidden": False},
        ),
    }


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def sample_item() -> Item:
    """Return a synthetic item with IVF-related content (source text)."""
    return Item(
        id="test-item-g5",
        source_name="pubmed",
        source_type="api",
        source_platform="pubmed",
        source_url="https://example.com/article",
        title="Test article about IVF outcomes",
        content=(
            "A recent study found that IVF success rates improve with "
            "time-lapse imaging. The live birth rate was 48.2% in the "
            "treatment group compared to 39.5% in the control group. "
            "This represents a statistically significant improvement."
        ),
        content_type="text",
        collected_at="2026-07-20T10:00:00Z",
        language="en",
        domain="medical-research",
        topic_tags=["IVF"],
        quality_tier=1,
    )


@pytest.fixture
def faithful_extraction() -> ExtractionResult:
    """Return an extraction result with a faithful translation in custom_fields."""
    return ExtractionResult(
        item_id="test-item-g5",
        title="Test article about IVF outcomes",
        tl_dr="IVF success rates improve with time-lapse imaging.",
        key_points=["Time-lapse imaging improves IVF outcomes"],
        entities=[{"name": "IVF", "type": "procedure", "relevance": 0.9}],
        relevance_score=90.0,
        custom_fields={
            "translation": (
                "Una recente studio ha scoperto che i tassi di successo della "
                "FIV migliorano con l'imaging time-lapse. Il tasso di nati vivi "
                "era del 48.2% nel gruppo di trattamento rispetto al 39.5% nel "
                "gruppo di controllo. Questo rappresenta un miglioramento "
                "statisticamente significativo."
            ),
        },
    )


@pytest.fixture
def unfaithful_extraction() -> ExtractionResult:
    """Return an extraction result with an unfaithful translation."""
    return ExtractionResult(
        item_id="test-item-g5",
        title="Test article about IVF outcomes",
        tl_dr="IVF success rates improve with time-lapse imaging.",
        key_points=["Time-lapse imaging improves IVF outcomes"],
        entities=[{"name": "IVF", "type": "procedure", "relevance": 0.9}],
        relevance_score=10.0,
        custom_fields={
            "translation": (
                "Uno studio recente ha scoperto che la FIV riduce i tassi di "
                "successo. Il tasso di nati vivi era solo del 10% e la "
                "procedura è considerata pericolosa."
            ),
        },
    )


@pytest.fixture
def no_translation_extraction() -> ExtractionResult:
    """Return an extraction result without translation in custom_fields."""
    return ExtractionResult(
        item_id="test-item-g5",
        title="Test article about IVF outcomes",
        tl_dr="IVF success rates improve with time-lapse imaging.",
        key_points=["Time-lapse imaging improves IVF outcomes"],
        entities=[{"name": "IVF", "type": "procedure", "relevance": 0.9}],
        relevance_score=90.0,
        custom_fields={},
    )


@pytest.fixture
def process_items() -> list[Item]:
    """Return synthetic items for pipeline integration tests."""
    return [
        Item(
            id="proc-item-g5",
            source_name="pubmed",
            source_type="api",
            source_platform="pubmed",
            source_url="https://example.com/1",
            title="Test article about IVF",
            content="Content about IVF treatment outcomes.",
            content_type="text",
            collected_at="2026-07-20T10:00:00Z",
            language="en",
            domain="medical-research",
            topic_tags=["IVF"],
            quality_tier=1,
            raw_data={},
        ),
    ]


@pytest.fixture
def process_extraction() -> ExtractionResult:
    """Return extraction result with translation for pipeline tests."""
    return ExtractionResult(
        item_id="proc-item-g5",
        title="Test article about IVF",
        tl_dr="A test summary about IVF outcomes.",
        key_points=["IVF is effective"],
        entities=[],
        relevance_score=85.0,
        custom_fields={
            "translation": "Una traduzione di prova sui risultati della FIV.",
        },
    )


# ===================================================================
# G5 — Unit Tests
# ===================================================================


class TestG5TranslationAccuracyCheck:
    """G5TranslationAccuracy.check() — direct unit tests with mocked LLM."""

    def test_passes_when_translation_is_faithful(
        self, sample_item: Item, faithful_extraction: ExtractionResult
    ) -> None:
        """LLM returns faithful=true → gate passes, not flagged."""
        mock_llm = _mock_litellm(
            {
                "faithful": True,
                "explanation": "Translation faithfully represents the source.",
                "issues": [],
            }
        )
        with patch("autoinfo.quality.call_with_fallback", return_value=mock_llm.completion.return_value):
            g5 = G5TranslationAccuracy(model="test/test")
            result = g5.check(sample_item, faithful_extraction)

        assert result.passed is True
        assert result.flagged is False
        assert result.details["faithful"] is True
        assert result.score == 1.0

    def test_flags_when_translation_is_unfaithful(
        self, sample_item: Item, unfaithful_extraction: ExtractionResult
    ) -> None:
        """LLM returns faithful=false → gate fails, flagged."""
        mock_llm = _mock_litellm(
            {
                "faithful": False,
                "explanation": "Translation changes the meaning significantly.",
                "issues": ["Changed 'improves' to 'reduces'", "Added negative claim about safety"],
            }
        )
        with patch("autoinfo.quality.call_with_fallback", return_value=mock_llm.completion.return_value):
            g5 = G5TranslationAccuracy(model="test/test")
            result = g5.check(sample_item, unfaithful_extraction)

        assert result.passed is False
        assert result.flagged is True
        assert result.details["faithful"] is False
        assert result.score == 0.0
        assert len(result.details["issues"]) == 2

    def test_handles_malformed_json(
        self, sample_item: Item, faithful_extraction: ExtractionResult
    ) -> None:
        """LLM returns invalid JSON → flagged as uncertain (faithful=None)."""
        mock_llm = _mock_litellm_raw("this is not json")
        with patch("autoinfo.quality.call_with_fallback", return_value=mock_llm.completion.return_value):
            g5 = G5TranslationAccuracy(model="test/test")
            result = g5.check(sample_item, faithful_extraction)

        assert result.passed is False
        assert result.flagged is True
        assert result.details["faithful"] is None
        assert "malformed" in result.details["explanation"].lower() or "parse" in result.details["explanation"].lower()

    def test_handles_incomplete_json(
        self, sample_item: Item, faithful_extraction: ExtractionResult
    ) -> None:
        """LLM returns JSON missing 'faithful' key → treated as unfaithful."""
        mock_llm = _mock_litellm({"explanation": "No faithful field", "issues": []})
        with patch("autoinfo.quality.call_with_fallback", return_value=mock_llm.completion.return_value):
            g5 = G5TranslationAccuracy(model="test/test")
            result = g5.check(sample_item, faithful_extraction)

        # Missing key defaults to faithful=False
        assert result.passed is False
        assert result.flagged is True
        assert result.details["faithful"] is False

    def test_skips_when_no_translation(
        self, sample_item: Item, no_translation_extraction: ExtractionResult
    ) -> None:
        """Empty translation returns trivially-passed result without LLM call."""
        g5 = G5TranslationAccuracy(model="test/test")
        result = g5.check(sample_item, no_translation_extraction)

        assert result.passed is True
        assert result.flagged is False
        assert result.details["faithful"] is True
        assert result.details["explanation"] == "No translation to check"

    def test_handles_litellm_unavailable(
        self, sample_item: Item, faithful_extraction: ExtractionResult
    ) -> None:
        """When litellm is not installed, return flagged result with explanation."""
        with patch("autoinfo.quality.call_with_fallback", side_effect=RuntimeError("litellm is not available")):
            g5 = G5TranslationAccuracy(model="test/test")
            result = g5.check(sample_item, faithful_extraction)

        assert result.passed is False
        assert result.flagged is True
        assert result.details["faithful"] is None
        assert "litellm is not available" in result.details["explanation"]

    def test_llm_exception_caught_gracefully(
        self, sample_item: Item, faithful_extraction: ExtractionResult
    ) -> None:
        """LLM raises an exception → returned as flagged uncertain."""
        mock_llm = MagicMock()
        mock_llm.completion.side_effect = RuntimeError("API timeout")
        with patch("autoinfo.quality.call_with_fallback", return_value=mock_llm.completion.return_value):
            g5 = G5TranslationAccuracy(model="test/test")
            result = g5.check(sample_item, faithful_extraction)

        assert result.passed is False
        assert result.flagged is True
        assert result.details["faithful"] is None
        assert "LLM check failed" in result.details["explanation"]

    def test_uses_custom_fields_translation(
        self, sample_item: Item, faithful_extraction: ExtractionResult
    ) -> None:
        """Translation is read from extraction.custom_fields['translation']."""
        mock_llm = _mock_litellm(
            {
                "faithful": True,
                "explanation": "Good translation.",
                "issues": [],
            }
        )
        with patch("autoinfo.quality.call_with_fallback", return_value=mock_llm.completion.return_value) as mock_cwf:
            g5 = G5TranslationAccuracy(model="test/test")
            result = g5.check(sample_item, faithful_extraction)

        assert result.passed is True
        # Verify the LLM was called with the translation text
        call_args = mock_cwf.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        assert "Una recente studio" in user_msg


# ===================================================================
# G5 — Frontmatter Integration
# ===================================================================


class TestG5Frontmatter:
    """G5 result appears in KB frontmatter when --check-translation is used."""

    def test_g5_included_in_frontmatter_when_present(self) -> None:
        """Quality results with G5 produce frontmatter with G5-TranslationAccuracy flag."""
        quality_results = _make_quality_results_base()
        quality_results["G5-TranslationAccuracy"] = QualityResult(
            gate_name="G5-TranslationAccuracy",
            passed=False,
            flagged=True,
            details={"faithful": False, "explanation": "Mismatch", "issues": ["wrong meaning"]},
        )

        entry = KBEntry(
            entry_id="test-entry",
            title="Test",
            domain="test",
        )
        frontmatter = _build_frontmatter(entry, quality_results)

        assert "G5-TranslationAccuracy" in frontmatter
        assert "quality_flags" in frontmatter

    def test_g5_absent_from_frontmatter_when_not_run(self) -> None:
        """Quality results without G5 produce frontmatter without G5 flag."""
        quality_results = _make_quality_results_base()

        entry = KBEntry(
            entry_id="test-entry",
            title="Test",
            domain="test",
        )
        frontmatter = _build_frontmatter(entry, quality_results)

        assert "G5-TranslationAccuracy" not in frontmatter
        # G1-G3 flags should still be present
        assert "G1-SourceAuthority" in frontmatter
        assert "G2-Dedup" in frontmatter
        assert "G3-RelevanceScoring" in frontmatter


# ===================================================================
# G5 — Pipeline Integration
# ===================================================================


class TestG5PipelineIntegration:
    """G5 gate integrated with run_processing()."""

    def test_g5_runs_when_check_translation(
        self,
        process_items: list[Item],
        process_extraction: ExtractionResult,
    ) -> None:
        """When --check-translation is set, G5 result is in quality_results."""
        mock_ext = MagicMock(return_value=process_extraction)
        mock_quality = MagicMock(return_value=_make_quality_results_base())

        mock_entry = KBEntry(entry_id="test", title="test", domain="test")
        mock_store = MagicMock(spec=KBStore)
        mock_store.store_entry.return_value = mock_entry
        mock_store.list_entries.return_value = []

        with (
            patch("autoinfo.process.load_cached_items", return_value=process_items),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.llm_judge") as mock_llm_judge,
            patch(
                "autoinfo.translation_qa.calculate_quality_score",
            ) as mock_calc_score,
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            mock_llm_judge.return_value = {
                "faithfulness": 85,
                "terminology": 80,
                "style": 75,
                "readability": 90,
                "issues": ["mock issue"],
            }
            mock_calc_score.return_value = {
                "composite": 82.5,
                "faithfulness": 85.0,
                "terminology": 80.0,
                "style": 75.0,
                "readability": 90.0,
            }

            result = run_processing("medical-research", check_translation=True)

        # Pipeline completed
        assert result.kb_entries_created == 1
        assert result.errors == []

        # Verify G5 result was passed to store_entry (3rd positional arg)
        call_args = mock_store.store_entry.call_args
        assert call_args is not None
        args, _ = call_args
        quality_results = args[2] if len(args) > 2 else {}
        assert "G5-TranslationAccuracy" in quality_results
        g5 = quality_results["G5-TranslationAccuracy"]
        assert g5.flagged is not True  # composite >= 50 → faithful
        assert g5.details.get("composite_score") == 82.5

        # Item log should contain g5 info and composite_score
        assert result.per_item_logs[0].get("g5_flagged") is not True
        assert result.per_item_logs[0].get("g5_composite_score") == 82.5

    def test_g5_skipped_without_flag(
        self,
        process_items: list[Item],
        process_extraction: ExtractionResult,
    ) -> None:
        """Without --check-translation, G5 is not invoked."""
        mock_ext = MagicMock(return_value=process_extraction)
        mock_quality = MagicMock(return_value=_make_quality_results_base())

        mock_entry = KBEntry(entry_id="test", title="test", domain="test")
        mock_store = MagicMock(spec=KBStore)
        mock_store.store_entry.return_value = mock_entry
        mock_store.list_entries.return_value = []

        with (
            patch("autoinfo.process.load_cached_items", return_value=process_items),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            with patch(
                "autoinfo.process.G5TranslationAccuracy",
                side_effect=AssertionError("G5 should not be called"),
            ):
                result = run_processing("medical-research", check_translation=False)

        assert result.kb_entries_created == 1
        # G5 should not appear in quality_results (3rd positional arg)
        call_args = mock_store.store_entry.call_args
        args, _ = call_args
        quality_results = args[2] if len(args) > 2 else {}
        assert "G5-TranslationAccuracy" not in quality_results

    def test_g5_failure_does_not_block_pipeline(
        self,
        process_items: list[Item],
        process_extraction: ExtractionResult,
    ) -> None:
        """When G5 raises an exception, pipeline continues to next item."""
        mock_ext = MagicMock(return_value=process_extraction)
        mock_quality = MagicMock(return_value=_make_quality_results_base())

        mock_entry = KBEntry(entry_id="test", title="test", domain="test")
        mock_store = MagicMock(spec=KBStore)
        mock_store.store_entry.return_value = mock_entry
        mock_store.list_entries.return_value = []

        with (
            patch("autoinfo.process.load_cached_items", return_value=process_items),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch(
                "autoinfo.process.llm_judge",
                side_effect=RuntimeError("G5 crashed"),
            ),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research", check_translation=True)

        # Pipeline still completed
        assert result.kb_entries_created == 1
        assert result.errors == []

        # The fallback G5 result should be in quality_results (3rd positional arg)
        call_args = mock_store.store_entry.call_args
        args, _ = call_args
        quality_results = args[2] if len(args) > 2 else {}
        assert "G5-TranslationAccuracy" in quality_results
        # The fallback result has faithful=None (uncertain)
        assert quality_results["G5-TranslationAccuracy"].details.get("faithful") is None

    def test_g5_passed_flag_in_item_log(
        self,
        process_items: list[Item],
        process_extraction: ExtractionResult,
    ) -> None:
        """Item log records g5_flagged, g5_faithful, and g5_composite_score."""
        mock_ext = MagicMock(return_value=process_extraction)
        mock_quality = MagicMock(return_value=_make_quality_results_base())

        mock_entry = KBEntry(entry_id="test", title="test", domain="test")
        mock_store = MagicMock(spec=KBStore)
        mock_store.store_entry.return_value = mock_entry
        mock_store.list_entries.return_value = []

        with (
            patch("autoinfo.process.load_cached_items", return_value=process_items),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.llm_judge") as mock_llm_judge,
            patch(
                "autoinfo.translation_qa.calculate_quality_score",
            ) as mock_calc_score,
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            mock_llm_judge.return_value = {
                "faithfulness": 30,
                "terminology": 25,
                "style": 20,
                "readability": 40,
                "issues": ["mock unfaithful", "wrong terms"],
            }
            mock_calc_score.return_value = {
                "composite": 28.5,
                "faithfulness": 30.0,
                "terminology": 25.0,
                "style": 20.0,
                "readability": 40.0,
            }

            result = run_processing("medical-research", check_translation=True)

        log = result.per_item_logs[0]
        assert log.get("g5_flagged") is True
        assert log.get("g5_faithful") is False
        assert log.get("g5_composite_score") == 28.5
