"""Tests for autoinfo.translation_qa LLM-call paths.

All LLM traffic is mocked at ``autoinfo.translation_qa.call_with_fallback``
(no network, no config file needed): explicit model / model_pool / timeout
arguments keep the tests hermetic, mirroring the G4/G5 gate-test convention.

- ``back_translate`` — pool selection, success, empty response, failure,
  timeout resolution
- ``llm_judge_translation`` — score clamping, issue normalization, malformed
  and failed LLM calls, unconfigured-deployment error (#195), json_mode flag
- ``refine_translation`` — feedback formatting, success, empty response,
  failure fallback to the initial translation
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.config import JudgmentModelNotConfiguredError
from autoinfo.translation_qa import (
    back_translate,
    llm_judge_translation,
    refine_translation,
)


def _response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = text
    return resp


# ---------------------------------------------------------------------------
# back_translate
# ---------------------------------------------------------------------------


class TestBackTranslate:
    def test_second_pool_model_is_used_for_back_translation(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response("  back-translated text\n"),
        ) as mock_call:
            result = back_translate(
                "source text",
                "translated text",
                "en",
                "zh",
                model_pool=["test/model-a", "test/model-b"],
                timeout=9.0,
            )
        assert result == {
            "back_translated_text": "back-translated text",
            "back_model": "test/model-b",
            "forward_model": "test/model-a",
            "success": True,
        }
        kwargs = mock_call.call_args.kwargs
        assert kwargs["model"] == "test/model-b"
        assert kwargs["max_tokens"] == 4000
        assert kwargs["temperature"] == 0.1
        assert kwargs["timeout"] == 9.0

    def test_single_model_pool_reuses_same_model(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response("back"),
        ) as mock_call:
            result = back_translate("s", "t", "en", "zh", model_pool=["test/model-a"], timeout=5.0)
        assert result["forward_model"] == result["back_model"] == "test/model-a"
        assert mock_call.call_args.kwargs["model"] == "test/model-a"

    def test_empty_response_reports_failure(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response("   \n"),
        ):
            result = back_translate("s", "t", "en", "zh", model_pool=["test/model-a"], timeout=5.0)
        assert result["success"] is False
        assert result["back_translated_text"] == ""
        assert result["back_model"] == "test/model-a"

    def test_llm_failure_reports_failure(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            side_effect=RuntimeError("connection refused"),
        ):
            result = back_translate("s", "t", "en", "zh", model_pool=["test/model-a"], timeout=5.0)
        assert result["success"] is False
        assert result["back_translated_text"] == ""

    def test_timeout_none_resolves_from_config_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("autoinfo.config.get_config_path", lambda: None)
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response("back"),
        ) as mock_call:
            back_translate("s", "t", "en", "zh", model_pool=["test/model-a"])
        assert mock_call.call_args.kwargs["timeout"] == 120.0


# ---------------------------------------------------------------------------
# llm_judge_translation
# ---------------------------------------------------------------------------


class TestLlmJudgeTranslation:
    def test_successful_judgment_normalizes_issues(self) -> None:
        payload = {
            "faithfulness_score": 87.5,
            "issues": [
                {
                    "severity": "major",
                    "description": "dropped nuance",
                    "position": "paragraph 2",
                },
                {"severity": 7, "position": None},  # partially specified entry
                "not a dict",  # non-dict entries are dropped
            ],
        }
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response(json.dumps(payload)),
        ) as mock_call:
            result = llm_judge_translation(
                "original", "back-translated", "en", model="test/judge", timeout=4.0
            )
        assert result["faithfulness_score"] == 87.5
        assert result["issues"] == [
            {
                "severity": "major",
                "description": "dropped nuance",
                "position": "paragraph 2",
            },
            {"severity": "7", "description": "", "position": "None"},
        ]
        kwargs = mock_call.call_args.kwargs
        assert kwargs["model"] == "test/judge"
        assert kwargs["max_tokens"] == 2000
        assert kwargs["temperature"] == 0.1
        assert kwargs["disable_thinking"] is False

    @pytest.mark.parametrize(
        ("raw_score", "expected"),
        [(150, 100.0), (-5, 0.0), (0, 0.0)],
    )
    def test_faithfulness_score_is_clamped(self, raw_score: float, expected: float) -> None:
        payload = json.dumps({"faithfulness_score": raw_score, "issues": []})
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response(payload),
        ):
            result = llm_judge_translation("o", "b", "en", model="test/judge", timeout=1.0)
        assert result["faithfulness_score"] == expected

    def test_missing_score_defaults_to_zero(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response(json.dumps({"issues": []})),
        ):
            result = llm_judge_translation("o", "b", "en", model="test/judge", timeout=1.0)
        assert result["faithfulness_score"] == 0.0
        assert result["issues"] == []

    def test_malformed_json_reports_parse_failure(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response("this is not json {"),
        ):
            result = llm_judge_translation("o", "b", "en", model="test/judge", timeout=1.0)
        assert result["faithfulness_score"] == 0.0
        issue = result["issues"][0]
        assert issue["severity"] == "major"
        assert issue["description"].startswith("Failed to parse LLM response")
        assert issue["position"] == "n/a"

    def test_llm_call_failure_is_reported(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            side_effect=RuntimeError("gateway down"),
        ):
            result = llm_judge_translation("o", "b", "en", model="test/judge", timeout=1.0)
        assert result["faithfulness_score"] == 0.0
        issue = result["issues"][0]
        assert issue["description"] == "LLM evaluation failed: gateway down"

    def test_unconfigured_deployment_raises_loudly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("autoinfo.config.get_config_path", lambda: None)
        with pytest.raises(JudgmentModelNotConfiguredError):
            llm_judge_translation("o", "b", "en", timeout=1.0)

    def test_timeout_none_resolves_from_config_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("autoinfo.config.get_config_path", lambda: None)
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response(json.dumps({"faithfulness_score": 50})),
        ) as mock_call:
            llm_judge_translation("o", "b", "en", model="test/judge")
        assert mock_call.call_args.kwargs["timeout"] == 120.0

    def test_json_mode_flag_is_forwarded(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response(json.dumps({"faithfulness_score": 50})),
        ) as mock_call:
            llm_judge_translation("o", "b", "en", model="test/judge", json_mode=True, timeout=1.0)
        assert mock_call.call_args.kwargs["json_mode"] is True


# ---------------------------------------------------------------------------
# refine_translation
# ---------------------------------------------------------------------------


class TestRefineTranslation:
    def test_successful_refinement_formats_feedback_into_prompt(self) -> None:
        feedback = [
            {
                "severity": "major",
                "description": "wrong term for IVF",
                "position": "sentence 1",
            },
            {"severity": "minor", "description": "tone too casual", "position": ""},
        ]
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response("  improved translation  \n"),
        ) as mock_call:
            result = refine_translation(
                "source text",
                "flawed translation",
                "en",
                "zh",
                feedback,
                model="test/refiner",
                timeout=6.0,
            )
        assert result == {"translation": "improved translation", "model_used": "test/refiner"}
        messages = mock_call.call_args.kwargs["messages"]
        user_prompt: str = messages[-1]["content"]
        assert "1. [major] wrong term for IVF (location: sentence 1)" in user_prompt
        assert "2. [minor] tone too casual" in user_prompt
        assert "source text" in user_prompt
        assert mock_call.call_args.kwargs["temperature"] == 0.1

    def test_empty_feedback_uses_generic_issue_text(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response("better"),
        ) as mock_call:
            refine_translation("s", "initial", "en", "zh", [], model="test/refiner", timeout=1.0)
        user_prompt: str = mock_call.call_args.kwargs["messages"][-1]["content"]
        assert "No specific issues were identified" in user_prompt

    def test_empty_response_falls_back_to_initial_translation(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response("   "),
        ):
            result = refine_translation(
                "s", "initial translation", "en", "zh", [], model="m", timeout=1.0
            )
        assert result == {"translation": "initial translation", "model_used": "m"}

    def test_llm_failure_falls_back_to_initial_translation(self) -> None:
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            side_effect=RuntimeError("boom"),
        ):
            result = refine_translation(
                "s", "initial translation", "en", "zh", [], model="m", timeout=1.0
            )
        assert result == {"translation": "initial translation", "model_used": "m"}

    def test_timeout_none_resolves_from_config_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("autoinfo.config.get_config_path", lambda: None)
        with patch(
            "autoinfo.translation_qa.call_with_fallback",
            return_value=_response("better"),
        ) as mock_call:
            refine_translation("s", "initial", "en", "zh", [], model="test/refiner")
        assert mock_call.call_args.kwargs["timeout"] == 120.0

    def test_model_resolution_failure_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("autoinfo.config.get_config_path", lambda: None)
        with pytest.raises(JudgmentModelNotConfiguredError):
            refine_translation("s", "initial", "en", "zh", [], timeout=1.0)
