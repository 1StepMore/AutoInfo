"""Tests for autoinfo.translation_qa composite scoring and rounds list.

Pure-function coverage (no LLM, no config):

- ``calculate_quality_score`` — weighted composite, clamping, None defaults,
  weight normalization, zero-total weight fallback, unknown-weight keys
- ``_build_rounds_list`` — per-round diagnostics from pipeline candidates
"""

from __future__ import annotations

from autoinfo.translation_qa import DEFAULT_WEIGHTS, _build_rounds_list, calculate_quality_score


class TestCalculateQualityScore:
    def test_exact_weighted_composite_with_default_weights(self) -> None:
        result = calculate_quality_score(faithfulness=90, terminology=80, style=70, readability=60)
        # 0.4*90 + 0.3*80 + 0.2*70 + 0.1*60 = 36 + 24 + 14 + 6 = 80
        assert result["composite"] == 80.0
        assert result["faithfulness"] == 90.0
        assert result["terminology"] == 80.0
        assert result["style"] == 70.0
        assert result["readability"] == 60.0
        assert result["weights_used"] == {
            "faithfulness": 40.0,
            "terminology": 30.0,
            "style": 20.0,
            "readability": 10.0,
        }

    def test_scores_are_clamped_to_unit_range(self) -> None:
        result = calculate_quality_score(
            faithfulness=150, terminology=-10, style=100, readability=0
        )
        assert result["faithfulness"] == 100.0
        assert result["terminology"] == 0.0
        assert result["composite"] == 60.0

    def test_missing_scores_default_to_zero(self) -> None:
        result = calculate_quality_score(faithfulness=50)
        assert result["terminology"] == 0.0
        assert result["style"] == 0.0
        assert result["readability"] == 0.0
        assert result["composite"] == 20.0

    def test_all_none_scores_yield_zero_composite(self) -> None:
        result = calculate_quality_score()
        assert result["composite"] == 0.0

    def test_custom_weights_are_normalized(self) -> None:
        result = calculate_quality_score(
            faithfulness=100,
            terminology=0,
            style=0,
            readability=0,
            weights={"faithfulness": 2, "terminology": 2, "style": 1, "readability": 1},
        )
        assert result["composite"] == 33.3
        assert result["weights_used"]["faithfulness"] == 33.3
        assert result["weights_used"]["readability"] == 16.7

    def test_zero_total_weight_falls_back_to_defaults(self) -> None:
        result = calculate_quality_score(
            faithfulness=100,
            weights={"faithfulness": 0, "terminology": 0, "style": 0, "readability": 0},
        )
        assert result["composite"] == 40.0
        assert result["weights_used"] == {
            "faithfulness": 40.0,
            "terminology": 30.0,
            "style": 20.0,
            "readability": 10.0,
        }

    def test_weights_missing_dimensions_count_as_zero(self) -> None:
        result = calculate_quality_score(faithfulness=50, weights={"faithfulness": 100})
        assert result["composite"] == 50.0
        assert result["weights_used"] == {"faithfulness": 100.0}

    def test_default_weights_constant_shape(self) -> None:
        assert DEFAULT_WEIGHTS == {
            "faithfulness": 40,
            "terminology": 30,
            "style": 20,
            "readability": 10,
        }


class TestBuildRoundsList:
    def test_rounds_from_mixed_candidates(self) -> None:
        candidates = [
            (
                "initial",
                "m/a",
                {"faithfulness": 85.0, "composite_score": 34.0, "issues": [{"severity": "minor"}]},
            ),
            ("refined-1", "m/b", None),
            ("refined-2", "m/b", {"faithfulness": 95.0, "composite_score": 38.0}),
        ]
        rounds = _build_rounds_list(candidates)
        assert [r["round"] for r in rounds] == [1, 2, 3]
        assert rounds[0] == {
            "round": 1,
            "model_used": "m/a",
            "faithfulness": 85.0,
            "composite": 34.0,
            "issues": [{"severity": "minor"}],
        }
        assert rounds[1] == {
            "round": 2,
            "model_used": "m/b",
            "faithfulness": 0.0,
            "composite": 0.0,
            "issues": [],
        }
        assert rounds[2]["composite"] == 38.0

    def test_empty_candidates_yield_empty_rounds(self) -> None:
        assert _build_rounds_list([]) == []

    def test_evaluation_issues_are_copied_not_shared(self) -> None:
        issues: list = [{"severity": "major"}]
        rounds = _build_rounds_list(
            [("t", "m", {"faithfulness": 0, "composite_score": 0, "issues": issues})]
        )
        rounds[0]["issues"].append({"severity": "minor"})
        assert issues == [{"severity": "major"}]
