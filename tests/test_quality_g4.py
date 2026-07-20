"""Tests for G4 factual consistency gate.

Covers:
    - G4FactualConsistency.check() with contradiction detected
    - G4FactualConsistency.check() with consistent summary
    - G4FactualConsistency.check() with malformed LLM response
    - G4FactualConsistency.check() with empty summary (skip)
    - G4FactualConsistency.check() when litellm is unavailable
    - G4 result stored in KB frontmatter via run_processing (--check-factual)
    - Without --check-factual, G4 is skipped
    - G4 failure doesn't block the pipeline
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
    G4FactualConsistency,
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
    """Return a synthetic item with IVF-related content."""
    return Item(
        id="test-item-g4",
        source_name="pubmed",
        source_type="api",
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
def sample_extraction() -> ExtractionResult:
    """Return an extraction result with matching summary."""
    return ExtractionResult(
        item_id="test-item-g4",
        title="Test article about IVF outcomes",
        tl_dr="IVF success rates improve with time-lapse imaging. Live birth rate increased from 39.5% to 48.2%.",
        key_points=["Time-lapse imaging improves IVF outcomes"],
        entities=[{"name": "IVF", "type": "procedure", "relevance": 0.9}],
        relevance_score=90.0,
    )


@pytest.fixture
def contradictory_extraction() -> ExtractionResult:
    """Return an extraction result whose summary contradicts the source."""
    return ExtractionResult(
        item_id="test-item-g4",
        title="Test article about IVF outcomes",
        tl_dr="IVF success rates decrease with time-lapse imaging. Live birth rate dropped from 48.2% to 39.5%.",
        key_points=["Time-lapse imaging harms IVF outcomes"],
        entities=[{"name": "IVF", "type": "procedure", "relevance": 0.9}],
        relevance_score=10.0,
    )


@pytest.fixture
def process_items() -> list[Item]:
    """Return synthetic items for pipeline integration tests."""
    return [
        Item(
            id="proc-item-001",
            source_name="pubmed",
            source_type="api",
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
    """Return extraction result for pipeline tests."""
    return ExtractionResult(
        item_id="proc-item-001",
        title="Test article about IVF",
        tl_dr="A test summary about IVF outcomes.",
        key_points=["IVF is effective"],
        entities=[],
        relevance_score=85.0,
    )


# ===================================================================
# G4 — Unit Tests
# ===================================================================


class TestG4FactualConsistencyCheck:
    """G4FactualConsistency.check() — direct unit tests with mocked LLM."""

    def test_passes_when_summary_matches_source(
        self, sample_item: Item, sample_extraction: ExtractionResult
    ) -> None:
        """LLM returns contradiction=false → gate passes, not flagged."""
        mock_llm = _mock_litellm(
            {"contradiction": False, "explanation": "Summary matches source."}
        )
        with patch.object(G4FactualConsistency, "_get_litellm", return_value=mock_llm):
            g4 = G4FactualConsistency(model="test/test")
            result = g4.check(sample_item, sample_extraction)

        assert result.passed is True
        assert result.flagged is False
        assert result.details["contradiction"] is False
        assert result.score == 1.0

    def test_flags_when_summary_contradicts_source(
        self, sample_item: Item, contradictory_extraction: ExtractionResult
    ) -> None:
        """LLM returns contradiction=true → gate fails, flagged."""
        mock_llm = _mock_litellm(
            {
                "contradiction": True,
                "explanation": "Summary says decrease but source says increase.",
            }
        )
        with patch.object(G4FactualConsistency, "_get_litellm", return_value=mock_llm):
            g4 = G4FactualConsistency(model="test/test")
            result = g4.check(sample_item, contradictory_extraction)

        assert result.passed is False
        assert result.flagged is True
        assert result.details["contradiction"] is True
        assert result.score == 0.0

    def test_handles_malformed_json(
        self, sample_item: Item, sample_extraction: ExtractionResult
    ) -> None:
        """LLM returns invalid JSON → flagged as uncertain (contradiction=None)."""
        mock_llm = _mock_litellm_raw("this is not json")
        with patch.object(G4FactualConsistency, "_get_litellm", return_value=mock_llm):
            g4 = G4FactualConsistency(model="test/test")
            result = g4.check(sample_item, sample_extraction)

        assert result.passed is False
        assert result.flagged is True
        assert result.details["contradiction"] is None
        assert "malformed" in result.details["explanation"].lower() or "parse" in result.details["explanation"].lower()

    def test_handles_incomplete_json(
        self, sample_item: Item, sample_extraction: ExtractionResult
    ) -> None:
        """LLM returns JSON missing 'contradiction' key → treated as no contradiction."""
        mock_llm = _mock_litellm({"explanation": "No contradiction field"})
        with patch.object(G4FactualConsistency, "_get_litellm", return_value=mock_llm):
            g4 = G4FactualConsistency(model="test/test")
            result = g4.check(sample_item, sample_extraction)

        # Missing key defaults to contradiction=False
        assert result.passed is True
        assert result.flagged is False
        assert result.details["contradiction"] is False

    def test_skips_when_no_summary(
        self, sample_item: Item, sample_extraction: ExtractionResult
    ) -> None:
        """Empty TL;DR returns trivially-passed result without LLM call."""
        empty_extraction = ExtractionResult(
            item_id="test", title="Test", tl_dr=""
        )
        g4 = G4FactualConsistency(model="test/test")
        result = g4.check(sample_item, empty_extraction)

        assert result.passed is True
        assert result.flagged is False
        assert result.details["contradiction"] is False
        assert result.details["explanation"] == "No summary to check"

    def test_handles_litellm_unavailable(
        self, sample_item: Item, sample_extraction: ExtractionResult
    ) -> None:
        """When litellm is not installed, return flagged result with explanation."""
        with patch.object(G4FactualConsistency, "_get_litellm", return_value=None):
            g4 = G4FactualConsistency(model="test/test")
            result = g4.check(sample_item, sample_extraction)

        assert result.passed is False
        assert result.flagged is True
        assert result.details["contradiction"] is None
        assert "litellm is not available" in result.details["explanation"]

    def test_llm_exception_caught_gracefully(
        self, sample_item: Item, sample_extraction: ExtractionResult
    ) -> None:
        """LLM raises an exception → returned as flagged uncertain."""
        mock_llm = MagicMock()
        mock_llm.completion.side_effect = RuntimeError("API timeout")
        with patch.object(G4FactualConsistency, "_get_litellm", return_value=mock_llm):
            g4 = G4FactualConsistency(model="test/test")
            result = g4.check(sample_item, sample_extraction)

        assert result.passed is False
        assert result.flagged is True
        assert result.details["contradiction"] is None
        assert "LLM check failed" in result.details["explanation"]


# ===================================================================
# G4 — Frontmatter Integration
# ===================================================================


class TestG4Frontmatter:
    """G4 result appears in KB frontmatter when --check-factual is used."""

    def test_g4_included_in_frontmatter_when_present(self) -> None:
        """Quality results with G4 produce frontmatter with G4-SummaryFactual flag."""
        quality_results = _make_quality_results_base()
        quality_results["G4-SummaryFactual"] = QualityResult(
            gate_name="G4-SummaryFactual",
            passed=False,
            flagged=True,
            details={"contradiction": True, "explanation": "Mismatch"},
        )

        entry = KBEntry(
            entry_id="test-entry",
            title="Test",
            domain="test",
        )
        frontmatter = _build_frontmatter(entry, quality_results)

        assert "G4-SummaryFactual" in frontmatter
        assert "quality_flags" in frontmatter

    def test_g4_absent_from_frontmatter_when_not_run(self) -> None:
        """Quality results without G4 produce frontmatter without G4 flag."""
        quality_results = _make_quality_results_base()

        entry = KBEntry(
            entry_id="test-entry",
            title="Test",
            domain="test",
        )
        frontmatter = _build_frontmatter(entry, quality_results)

        assert "G4-SummaryFactual" not in frontmatter
        # G1-G3 flags should still be present
        assert "G1-SourceAuthority" in frontmatter
        assert "G2-Dedup" in frontmatter
        assert "G3-RelevanceScoring" in frontmatter


# ===================================================================
# G4 — Pipeline Integration
# ===================================================================


class TestG4PipelineIntegration:
    """G4 gate integrated with run_processing()."""

    def test_g4_runs_when_check_factual(
        self,
        process_items: list[Item],
        process_extraction: ExtractionResult,
    ) -> None:
        """When --check-factual is set, G4 result is in quality_results."""
        mock_ext = MagicMock(return_value=process_extraction)
        mock_quality = MagicMock(return_value=_make_quality_results_base())
        # Mock G4 to return a contradiction
        mock_g4_result = QualityResult(
            gate_name="G4-SummaryFactual",
            passed=False,
            flagged=True,
            details={"contradiction": True, "explanation": "Mock contradiction"},
        )

        mock_entry = KBEntry(entry_id="test", title="test", domain="test")
        mock_store = MagicMock(spec=KBStore)
        mock_store.store_entry.return_value = mock_entry
        mock_store.list_entries.return_value = []

        with (
            patch("autoinfo.process.load_cached_items", return_value=process_items),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.G4FactualConsistency") as mock_g4_cls,
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            mock_g4_instance = MagicMock()
            mock_g4_instance.check.return_value = mock_g4_result
            mock_g4_cls.return_value = mock_g4_instance

            result = run_processing("medical-research", check_factual=True)

        # Pipeline completed
        assert result.kb_entries_created == 1
        assert result.errors == []

        # Verify G4 was called
        mock_g4_instance.check.assert_called_once()

        # Verify G4 result was passed to store_entry (3rd positional arg)
        call_args = mock_store.store_entry.call_args
        assert call_args is not None
        args, _ = call_args
        quality_results = args[2] if len(args) > 2 else {}
        assert "G4-SummaryFactual" in quality_results
        assert quality_results["G4-SummaryFactual"].flagged is True

        # Item log should contain g4 info
        assert result.per_item_logs[0].get("g4_flagged") is True

    def test_g4_skipped_without_flag(
        self,
        process_items: list[Item],
        process_extraction: ExtractionResult,
    ) -> None:
        """Without --check-factual, G4 is not invoked."""
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
            # patch G4FactualConsistency to fail if called
            with patch(
                "autoinfo.process.G4FactualConsistency",
                side_effect=AssertionError("G4 should not be called"),
            ):
                result = run_processing("medical-research", check_factual=False)

        assert result.kb_entries_created == 1
        # G4 should not appear in quality_results (3rd positional arg)
        call_args = mock_store.store_entry.call_args
        args, _ = call_args
        quality_results = args[2] if len(args) > 2 else {}
        assert "G4-SummaryFactual" not in quality_results

    def test_g4_failure_does_not_block_pipeline(
        self,
        process_items: list[Item],
        process_extraction: ExtractionResult,
    ) -> None:
        """When G4 raises an exception, pipeline continues to next item."""
        mock_ext = MagicMock(return_value=process_extraction)
        mock_quality = MagicMock(return_value=_make_quality_results_base())

        # Make G4 raise
        mock_g4_instance = MagicMock()
        mock_g4_instance.check.side_effect = RuntimeError("G4 crashed")

        mock_entry = KBEntry(entry_id="test", title="test", domain="test")
        mock_store = MagicMock(spec=KBStore)
        mock_store.store_entry.return_value = mock_entry
        mock_store.list_entries.return_value = []

        with (
            patch("autoinfo.process.load_cached_items", return_value=process_items),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.G4FactualConsistency", return_value=mock_g4_instance),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research", check_factual=True)

        # Pipeline still completed
        assert result.kb_entries_created == 1
        assert result.errors == []

        # The fallback G4 result should be in quality_results (3rd positional arg)
        call_args = mock_store.store_entry.call_args
        args, _ = call_args
        quality_results = args[2] if len(args) > 2 else {}
        assert "G4-SummaryFactual" in quality_results
        # The fallback result has contradiction=None (uncertain)
        assert quality_results["G4-SummaryFactual"].details.get("contradiction") is None

    def test_g4_passed_flag_in_item_log(
        self,
        process_items: list[Item],
        process_extraction: ExtractionResult,
    ) -> None:
        """Item log records g4_flagged and g4_contradiction."""
        mock_ext = MagicMock(return_value=process_extraction)
        mock_quality = MagicMock(return_value=_make_quality_results_base())
        mock_g4_result = QualityResult(
            gate_name="G4-SummaryFactual",
            passed=False,
            flagged=True,
            details={"contradiction": True, "explanation": "Mock contradiction"},
        )
        mock_g4_check = MagicMock(return_value=mock_g4_result)

        mock_entry = KBEntry(entry_id="test", title="test", domain="test")
        mock_store = MagicMock(spec=KBStore)
        mock_store.store_entry.return_value = mock_entry
        mock_store.list_entries.return_value = []

        with (
            patch("autoinfo.process.load_cached_items", return_value=process_items),
            patch.object(LLMExtractor, "extract", mock_ext),
            patch("autoinfo.process.run_quality_gates", mock_quality),
            patch("autoinfo.process.G4FactualConsistency") as mock_g4_cls,
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            mock_g4_instance = MagicMock()
            mock_g4_instance.check.return_value = mock_g4_result
            mock_g4_cls.return_value = mock_g4_instance

            result = run_processing("medical-research", check_factual=True)

        log = result.per_item_logs[0]
        assert log.get("g4_flagged") is True
        assert log.get("g4_contradiction") is True
