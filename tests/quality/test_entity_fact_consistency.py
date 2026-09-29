"""Tests for G7 — deterministic Entity/Number Fact Consistency gate.

G7 flags numeric claims in an LLM extraction that are NOT derivable from the
source item.  It is **deterministic**: no LLM call, no network, same input →
same output.  It is **soft by default** (``action="flag"``) because the
dominant failure mode is over-flagging a legitimate paraphrase; operators can
raise it to ``block`` per-domain via ``quality_gates.G7``.

The single most important property is the honest-hedge invariant
(issues #179/#191): a sentence that says "not disclosed" / "未披露" is
CORRECT and must never be flagged.

Covers:
    - fabricated number absent from the source → flagged
    - honest hedge (EN + ZH) → NOT flagged, including a fabricated number that
      sits in the same hedged sentence
    - rounded / recast numbers derivable from the source → NOT flagged
    - thousands separators, K/M/B suffixes, percent/fraction, Chinese numerals
    - determinism + no LLM/network call in the gate path
    - config key registration + default soft/flag action
    - process.py post-extraction wiring
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from autoinfo.config import QualityGateConfig
from autoinfo.kb import KBStore
from autoinfo.kb import _build_frontmatter as build_frontmatter
from autoinfo.llm import LLMExtractor
from autoinfo.models import ExtractionResult, Item, KBEntry
from autoinfo.process import run_processing
from autoinfo.quality import G7EntityFactConsistency

GATE_NAME = "G7-EntityFactConsistency"

SOURCE = (
    "The trial enrolled 500 patients. The live birth rate was 48.2% in the "
    "treatment arm versus 39.5% in the control arm. Annual revenue was "
    "$1,200,000 (1.2 million). In 2024, spending reached 五百万 yuan."
)


def _make_item(content: str = SOURCE, title: str = "IVF outcomes and revenue") -> Item:
    return Item(
        id="test-item-g7",
        source_name="pubmed",
        source_type="api",
        source_platform="pubmed",
        source_url="https://example.com/g7",
        title=title,
        content=content,
        content_type="text",
        collected_at="2026-09-20T10:00:00Z",
        language="en",
        domain="medical-research",
        topic_tags=["IVF"],
        quality_tier=1,
    )


def _make_extraction(
    tl_dr: str, entities: list[dict[str, object]] | None = None
) -> ExtractionResult:
    return ExtractionResult(
        item_id="test-item-g7",
        title="IVF outcomes and revenue",
        tl_dr=tl_dr,
        key_points=[],
        entities=entities or [],
        relevance_score=90.0,
    )


# ===================================================================
# Core detection
# ===================================================================


class TestG7Detection:
    def test_flags_fabricated_number_absent_from_source(self) -> None:
        """A number that appears nowhere in the source is flagged."""
        result = G7EntityFactConsistency().check(
            _make_item(),
            _make_extraction("The live birth rate reached 95.7% in the treatment arm."),
        )

        assert result.gate_name == GATE_NAME
        assert result.flagged is True
        assert result.passed is True  # soft default — advisory flag only
        assert result.details["action"] == "flag"
        claims = result.details["unsupported_claims"]
        assert isinstance(claims, list)
        assert any("95.7" in str(c.get("claim")) for c in claims)

    def test_passes_when_all_numbers_are_in_source(self) -> None:
        result = G7EntityFactConsistency().check(
            _make_item(),
            _make_extraction("The trial enrolled 500 patients; live birth rate was 48.2%."),
        )

        assert result.flagged is False
        assert result.passed is True
        assert result.details["unsupported_claims"] == []

    def test_no_claims_passes(self) -> None:
        result = G7EntityFactConsistency().check(
            _make_item(),
            _make_extraction("No numeric claims are made here."),
        )

        assert result.flagged is False
        assert result.passed is True
        assert result.score == 1.0


# ===================================================================
# Honest hedge invariant (#179 / #191) — the single most important test
# ===================================================================


class TestG7HonestHedge:
    @pytest.mark.parametrize(
        "hedged",
        [
            "The exact number was not disclosed; reports cite 999,999 participants.",
            "The exact number was not provided; reports cite 999,999 participants.",
            "The exact figure is not available; reports cite 999,999 participants.",
            "具体人数未披露，有报道称999,999名参与者。",
            "具体人数未提供，有报道称999,999名参与者。",
            "具体数据未明确，有报道称999,999名参与者。",
            "具体金额暂无数据，有报道称999,999元。",
            "具体人数不详，有报道称999,999名参与者。",
        ],
    )
    def test_hedged_sentence_never_flagged(self, hedged: str) -> None:
        """A hedged sentence is skipped entirely — even if it contains a number."""
        result = G7EntityFactConsistency().check(_make_item(), _make_extraction(hedged))

        assert result.flagged is False, result.details
        assert result.passed is True

    def test_unhedged_fabrication_still_flagged_alongside_hedge(self) -> None:
        """Hedging one sentence must not mask a fabricated number in another."""
        result = G7EntityFactConsistency().check(
            _make_item(),
            _make_extraction(
                "The number of patients was not disclosed. The trial reported a 95.7% success rate."
            ),
        )

        assert result.flagged is True
        claims = result.details["unsupported_claims"]
        assert isinstance(claims, list)
        assert len(claims) == 1
        assert "95.7" in str(claims[0].get("claim"))


# ===================================================================
# False-positive control: rounding / separators / units / Chinese numerals
# ===================================================================


class TestG7FalsePositiveControl:
    def test_rounded_number_derivable_from_source_not_flagged(self) -> None:
        result = G7EntityFactConsistency().check(
            _make_item(),
            _make_extraction("The live birth rate was about 48% in the treatment arm."),
        )

        assert result.flagged is False, result.details

    def test_thousands_separator_matches(self) -> None:
        result = G7EntityFactConsistency().check(
            _make_item(),
            _make_extraction("Annual revenue was $1,200,000."),
        )

        assert result.flagged is False, result.details

    def test_suffix_million_matches_expanded_source(self) -> None:
        result = G7EntityFactConsistency().check(
            _make_item(),
            _make_extraction("Annual revenue was $1.2 million."),
        )

        assert result.flagged is False, result.details

    def test_chinese_numeral_matches_arabic_suffix(self) -> None:
        result = G7EntityFactConsistency().check(
            _make_item(),
            _make_extraction("Spending reached 500万元 in 2024."),
        )

        assert result.flagged is False, result.details

    def test_percent_fraction_equivalence(self) -> None:
        item = _make_item(content="The observed rate was 0.482 of live births.", title="Rate")
        result = G7EntityFactConsistency().check(item, _make_extraction("The rate was 48.2%."))

        assert result.flagged is False, result.details


# ===================================================================
# Named-entity claims
# ===================================================================


class TestG7EntityClaims:
    def test_absent_named_entity_flagged(self) -> None:
        result = G7EntityFactConsistency().check(
            _make_item(),
            _make_extraction(
                "A study by Anthropic found the rate was 48.2%.",
                entities=[{"name": "Anthropic", "type": "organization"}],
            ),
        )

        assert result.flagged is True
        claims = result.details["unsupported_claims"]
        assert isinstance(claims, list)
        assert any(c.get("kind") == "entity" for c in claims)

    def test_all_caps_acronym_not_flagged_on_expansion(self) -> None:
        """An acronym whose expansion is in the source is not a fabrication."""
        item = _make_item(content="In vitro fertilization improves outcomes.", title="Fertility")
        result = G7EntityFactConsistency().check(
            item,
            _make_extraction("IVF improves outcomes.", entities=[{"name": "IVF"}]),
        )

        assert result.flagged is False, result.details


# ===================================================================
# Determinism / no-LLM / no-network
# ===================================================================


class TestG7Determinism:
    def test_same_input_twice_is_identical(self) -> None:
        item = _make_item()
        extraction = _make_extraction(
            "The trial enrolled 500 patients and reported a 95.7% success rate."
        )
        gate = G7EntityFactConsistency()

        first = gate.check(item, extraction)
        second = gate.check(item, extraction)

        assert first.flagged is True
        assert first.details == second.details
        assert first.passed == second.passed
        assert first.score == second.score

    def test_gate_never_calls_llm_or_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*args: object, **kwargs: object) -> None:
            raise AssertionError("G7 must be deterministic — it must not call the LLM")

        def _no_network(*args: object, **kwargs: object) -> None:
            raise AssertionError("G7 must be deterministic — it must not open a socket")

        monkeypatch.setattr("autoinfo.quality.call_with_fallback", _boom)
        monkeypatch.setattr("autoinfo.llm.call_with_fallback", _boom)
        monkeypatch.setattr("socket.socket", _no_network)

        result = G7EntityFactConsistency().check(
            _make_item(),
            _make_extraction("The trial reported a 95.7% success rate."),
        )

        assert result.flagged is True


# ===================================================================
# Config: block escalation + default registration
# ===================================================================


class TestG7Config:
    def test_block_action_makes_it_fail(self) -> None:
        config = QualityGateConfig(
            name=GATE_NAME,
            category="hard",
            action="block",
        )
        result = G7EntityFactConsistency().check(
            _make_item(),
            _make_extraction("The trial reported a 95.7% success rate."),
            gate_config=config,
        )

        assert result.flagged is True
        assert result.passed is False
        assert result.details["action"] == "block"

    def test_default_action_is_flag_and_soft(self) -> None:
        from autoinfo.config import (
            _DEFAULT_QUALITY_GATES,
            _GATE_CONFIG_KEY_MAP,
            default_quality_gates,
        )

        assert _GATE_CONFIG_KEY_MAP["G7"] == GATE_NAME
        assert _DEFAULT_QUALITY_GATES["G7"]["category"] == "soft"
        assert _DEFAULT_QUALITY_GATES["G7"]["action"] == "flag"
        gates = default_quality_gates()
        assert GATE_NAME in gates
        assert gates[GATE_NAME].action == "flag"


# ===================================================================
# Frontmatter transparency
# ===================================================================


class TestG7Frontmatter:
    def test_flag_lands_in_quality_flags(self) -> None:
        result = G7EntityFactConsistency().check(
            _make_item(),
            _make_extraction("The trial reported a 95.7% success rate."),
        )
        entry = KBEntry(entry_id="e1", title="t", domain="d")
        frontmatter = build_frontmatter(entry, {GATE_NAME: result})

        assert GATE_NAME in frontmatter
        assert "quality_flags" in frontmatter


# ===================================================================
# process.py integration (post-extraction, always-on)
# ===================================================================


def _base_quality_results() -> dict[str, object]:
    from autoinfo.quality import QualityResult

    return {
        "G1-SourceAuthority": QualityResult(gate_name="G1-SourceAuthority", passed=True),
        "G2-Dedup": QualityResult(gate_name="G2-Dedup", passed=True),
        "G3-RelevanceScoring": QualityResult(gate_name="G3-RelevanceScoring", passed=True),
    }


class TestG7PipelineIntegration:
    def test_g7_runs_and_is_passed_to_store(self) -> None:
        item = _make_item(content="Content about IVF treatment outcomes.")
        extraction = _make_extraction("IVF success reached 95.7% in the study.")

        mock_store = MagicMock(spec=KBStore)
        mock_store.store_entry.return_value = KBEntry(entry_id="test", title="test", domain="test")
        mock_store.list_entries.return_value = []

        with (
            patch("autoinfo.process.load_cached_items", return_value=[item]),
            patch.object(LLMExtractor, "extract", MagicMock(return_value=extraction)),
            patch(
                "autoinfo.process.run_quality_gates",
                MagicMock(return_value=_base_quality_results()),
            ),
            patch("autoinfo.process.KBStore", return_value=mock_store),
        ):
            result = run_processing("medical-research")

        assert result.errors == []
        call_args = mock_store.store_entry.call_args
        assert call_args is not None
        args, _ = call_args
        quality_results = args[2] if len(args) > 2 else {}
        assert GATE_NAME in quality_results
        assert quality_results[GATE_NAME].flagged is True
        assert result.per_item_logs[0].get("g7_flagged") is True

    def test_g7_block_action_skips_storage(self) -> None:
        from autoinfo.quality import QualityResult

        item = _make_item(content="Content about IVF treatment outcomes.")
        extraction = _make_extraction("IVF success reached 95.7% in the study.")

        block_result = QualityResult(
            gate_name=GATE_NAME,
            passed=False,
            flagged=True,
            details={"action": "block"},
        )
        mock_store = MagicMock(spec=KBStore)
        mock_store.list_entries.return_value = []

        with (
            patch("autoinfo.process.load_cached_items", return_value=[item]),
            patch.object(LLMExtractor, "extract", MagicMock(return_value=extraction)),
            patch(
                "autoinfo.process.run_quality_gates",
                MagicMock(return_value=_base_quality_results()),
            ),
            patch("autoinfo.process.KBStore", return_value=mock_store),
            patch("autoinfo.process.G7EntityFactConsistency") as mock_g7_cls,
        ):
            mock_g7_cls.return_value.check.return_value = block_result
            result = run_processing("medical-research")

        assert result.kb_entries_created == 0
        mock_store.store_entry.assert_not_called()
        assert result.per_item_logs[0].get("status") == "g7_blocked"
