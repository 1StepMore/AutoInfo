"""Tests for autoinfo.translation_qa pipeline orchestrators.

All LLM traffic is mocked at ``autoinfo.translation_qa.call_with_fallback``
with a stateful fake that distinguishes the three call kinds (back-translate,
judge, refine) by prompt markers — the real orchestration logic runs
unmodified. Explicit model pools + timeouts keep tests hermetic.

- ``run_back_translation_pipeline`` — disabled, back-translation failure
  partial diagnostics, full success path with composite scoring
- ``run_refinement_pipeline`` — early return at threshold, refinement
  improvement, pool-reuse warning path, best-candidate selection
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

from autoinfo.translation_qa import (
    run_back_translation_pipeline,
    run_refinement_pipeline,
)

_POOL = ["test/model-a", "test/model-b"]
_BT_TEXT = "back translated source text"
_REFINE_TEXTS = ("refined v1", "refined v2")


def _fake_llm(judge_scores: list[float]) -> Any:
    """Build a call_with_fallback replacement keyed by prompt markers.

    Call kinds are told apart by their user-prompt text: the judge prompt
    asks to "Evaluate faithfulness", the refiner prompt contains
    "IMPROVED TRANSLATION", everything else is a back-translation call.
    """
    state = {"judge": 0, "refine": 0}

    def _fake(model: str, messages: list[dict[str, str]], **kwargs: Any):
        user_prompt = messages[-1]["content"]
        if "Evaluate faithfulness" in user_prompt:
            idx = min(state["judge"], len(judge_scores) - 1)
            state["judge"] += 1
            payload = {
                "faithfulness_score": judge_scores[idx],
                "issues": [
                    {
                        "severity": "minor",
                        "description": f"issue from judge #{state['judge']}",
                        "position": "para 1",
                    }
                ],
            }
            return _response(json.dumps(payload))
        if "IMPROVED TRANSLATION" in user_prompt:
            idx = min(state["refine"], len(_REFINE_TEXTS) - 1)
            state["refine"] += 1
            return _response(_REFINE_TEXTS[idx])
        return _response(_BT_TEXT)

    return _fake


def _response(text: str):
    resp = type("Resp", (), {})()
    resp.choices = [type("Choice", (), {})()]
    resp.choices[0].message = type("Msg", (), {})()
    resp.choices[0].message.content = text
    return resp


# ---------------------------------------------------------------------------
# run_back_translation_pipeline
# ---------------------------------------------------------------------------


class TestRunBackTranslationPipeline:
    def test_disabled_pipeline_returns_none(self) -> None:
        assert (
            run_back_translation_pipeline("src", "trans", "en", "zh", enable_back_translation=False)
            is None
        )

    def test_back_translation_failure_returns_partial_diagnostics(self) -> None:
        def _fail(model: str, messages: list, **kwargs: Any):
            raise RuntimeError("gateway down")

        with patch("autoinfo.translation_qa.call_with_fallback", side_effect=_fail):
            result = run_back_translation_pipeline(
                "src", "trans", "en", "zh", model_pool=_POOL, timeout=5.0
            )
        assert result["round"] == 1
        assert result["forward_model"] == "test/model-a"
        assert result["back_model"] == "test/model-b"
        assert result["judge_model"] == "n/a"
        assert result["faithfulness"] == 0.0
        assert result["composite_score"] == 0.0
        assert result["issues"] == [
            {
                "severity": "major",
                "description": "Back-translation failed or returned empty",
                "position": "n/a",
            }
        ]

    def test_success_path_scores_faithfulness_into_composite(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            side_effect=_fake_llm([85.0]),
        ) as mock_call:
            result = run_back_translation_pipeline(
                "src", "trans", "en", "zh", model_pool=_POOL, timeout=5.0
            )
        assert result["forward_model"] == "test/model-a"
        assert result["back_model"] == "test/model-b"
        assert result["judge_model"] == "test/model-b"
        assert result["faithfulness"] == 85.0
        # Only faithfulness is scored by back-translation (40% weight).
        assert result["composite_score"] == 34.0
        assert result["issues"][0]["description"] == "issue from judge #1"
        # Two LLM calls: back-translation then judgment.
        assert mock_call.call_count == 2


# ---------------------------------------------------------------------------
# run_refinement_pipeline
# ---------------------------------------------------------------------------


class TestRunRefinementPipeline:
    def test_initial_score_at_threshold_returns_without_refinement(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            side_effect=_fake_llm([90.0]),
        ) as mock_call:
            result = run_refinement_pipeline(
                "src",
                "initial translation",
                "en",
                "zh",
                model_pool=_POOL,
                threshold=30.0,
                timeout=5.0,
            )
        # composite = 90 * 0.4 = 36.0 >= threshold 30 -> no refinement rounds.
        assert result["final_translation"] == "initial translation"
        assert result["best_round_index"] == 0
        assert len(result["rounds"]) == 1
        assert result["rounds"][0]["composite"] == 36.0
        assert mock_call.call_count == 2

    def test_refinement_improves_and_stops_at_threshold(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            side_effect=_fake_llm([50.0, 100.0]),
        ) as mock_call:
            result = run_refinement_pipeline(
                "src",
                "initial translation",
                "en",
                "zh",
                model_pool=_POOL,
                threshold=39.0,
                timeout=5.0,
            )
        # Round 1: composite 20.0 < 39 -> refine. Round 2: 40.0 >= 39 -> stop.
        assert result["final_translation"] == "refined v1"
        assert result["best_round_index"] == 1
        assert [r["composite"] for r in result["rounds"]] == [20.0, 40.0]
        assert result["rounds"][1]["model_used"] == "test/model-a"
        # bt + judge (initial) + refine + bt + judge (re-eval).
        assert mock_call.call_count == 5

    def test_single_model_pool_is_reused_for_later_rounds(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            side_effect=_fake_llm([50.0]),
        ) as mock_call:
            result = run_refinement_pipeline(
                "src",
                "initial translation",
                "en",
                "zh",
                model_pool=["test/model-a"],
                threshold=39.0,
                max_rounds=2,
                timeout=5.0,
            )
        # Threshold is never reached; best candidate is the initial one.
        assert result["final_translation"] == "initial translation"
        assert result["best_round_index"] == 0
        assert [r["model_used"] for r in result["rounds"]] == [
            "test/model-a",
            "test/model-a",
            "test/model-a",
        ]
        # bt + judge + refine + bt + judge + refine + bt + judge.
        assert mock_call.call_count == 8

    def test_second_pool_model_used_for_second_refinement_round(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            side_effect=_fake_llm([50.0]),
        ) as mock_call:
            result = run_refinement_pipeline(
                "src",
                "initial translation",
                "en",
                "zh",
                model_pool=_POOL,
                threshold=39.0,
                max_rounds=2,
                timeout=5.0,
            )
        assert [r["model_used"] for r in result["rounds"]] == [
            "test/model-a",
            "test/model-a",
            "test/model-b",
        ]
        assert mock_call.call_count == 8

    def test_failed_evaluation_keeps_best_available_candidate(self) -> None:
        def _always_fail(model: str, messages: list, **kwargs: Any):
            raise RuntimeError("down")

        with patch("autoinfo.translation_qa.call_with_fallback", side_effect=_always_fail):
            result = run_refinement_pipeline(
                "src",
                "initial translation",
                "en",
                "zh",
                model_pool=_POOL,
                threshold=39.0,
                max_rounds=1,
                timeout=5.0,
            )
        # Evaluations never produce a score; the initial candidate wins.
        assert result["final_translation"] == "initial translation"
        assert result["best_round_index"] == 0
        assert len(result["rounds"]) == 2
        assert result["rounds"][1]["model_used"] == "test/model-a"
        assert result["rounds"][1]["composite"] == 0.0
        assert result["rounds"][1]["issues"] == [
            {
                "severity": "major",
                "description": "Back-translation failed or returned empty",
                "position": "n/a",
            }
        ]
