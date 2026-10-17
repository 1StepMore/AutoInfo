"""Issue #178 — LLM JSON robustness regression tests.

Covers:

- :func:`autoinfo.llm.parse_json_response` handles plain JSON, markdown-
  fenced JSON (`` ```json `` and bare `` ``` ``), prose-prefixed JSON, and
  nested code blocks; raises ``json.JSONDecodeError`` on total failure.
- ``call_with_fallback`` with ``reasoning_model=True`` + ``json_mode=True``
  sends a request **without** ``response_format`` and still returns the
  (parseable) model response.
- Task-level ``max_tokens`` (``LLMTaskConfig``) overrides the effective call
  ``max_tokens`` instead of being dead config.
- G4 / G5 gates parse markdown-fenced LLM output (previously raised).
- CEFR classification is unaffected by the ``max_tokens`` bump.

All LLM calls are mocked — no real API calls are made.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.cefr import classify_text
from autoinfo.config import Config, LLMConfig, LLMTaskConfig, _resolve_task_llm_config
from autoinfo.llm import (
    LLMExtractor,
    call_with_fallback,
    parse_json_response,
    repair_json_once,
    salvage_fields,
)
from autoinfo.models import ExtractionResult, Item
from autoinfo.quality import G4FactualConsistency, G5TranslationAccuracy

# ===================================================================
# Helpers
# ===================================================================


def _mock_litellm(raw_text: str) -> MagicMock:
    """Build a mock ``litellm`` module whose ``completion()`` returns raw text."""
    mock_litellm = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = raw_text
    mock_litellm.completion.return_value = mock_response
    return mock_litellm


@pytest.fixture
def hermetic_default_config(tmp_path: Path) -> str:
    """Write a minimal config with **no** ``llm.max_tokens`` and return its path.

    Hermetic seam (T4, 2026-09-11): pointing the usage-site
    ``autoinfo.llm.get_config_path`` binding at this file keeps
    default-behavior assertions independent of the gitignored repo-root
    ``.autoinfo/config.yaml`` (which sets ``llm.max_tokens: 4000``).  See
    `tests/TRIAGE.md:206-215` for the usage-site patch pattern.
    """
    path = tmp_path / "config.yaml"
    path.write_text(
        "llm:\n  provider: openai\n  model: deepseek-v4-flash\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture
def sample_item() -> Item:
    """Return a synthetic item for gate tests."""
    return Item(
        id="test-item-178",
        source_name="pubmed",
        source_type="api",
        source_platform="pubmed",
        source_url="https://example.com/article",
        title="Test article about IVF outcomes",
        content=(
            "A recent study found that IVF success rates improve with "
            "time-lapse imaging. The live birth rate was 48.2% in the "
            "treatment group compared to 39.5% in the control group."
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
        item_id="test-item-178",
        title="Test article about IVF outcomes",
        tl_dr=(
            "IVF success rates improve with time-lapse imaging. Live birth "
            "rate increased from 39.5% to 48.2%."
        ),
        key_points=["Time-lapse imaging improves IVF outcomes"],
        entities=[{"name": "IVF", "type": "procedure", "relevance": 0.9}],
        relevance_score=90.0,
    )


# ===================================================================
# parse_json_response
# ===================================================================


class TestParseJsonResponse:
    """The shared 3-strategy JSON extractor contract."""

    def test_plain_json(self) -> None:
        """A bare JSON object parses."""
        assert parse_json_response('{"a": 1}') == {"a": 1}

    def test_json_fenced(self) -> None:
        """```json fenced JSON parses."""
        text = '```json\n{"contradiction": false, "explanation": "ok"}\n```'
        assert parse_json_response(text) == {
            "contradiction": False,
            "explanation": "ok",
        }

    def test_bare_fenced(self) -> None:
        """Bare ``` fenced JSON (no language tag) parses."""
        text = '```\n{"faithful": true}\n```'
        assert parse_json_response(text) == {"faithful": True}

    def test_prose_prefixed(self) -> None:
        """JSON preceded by prose parses via the brace-extraction strategy."""
        text = 'Here is the assessment: {"contradiction": true, "explanation": "x"}'
        assert parse_json_response(text) == {
            "contradiction": True,
            "explanation": "x",
        }

    def test_nested_codeblock_in_prose(self) -> None:
        """A fenced block embedded inside surrounding prose parses."""
        text = (
            "The model produced:\n```json\n"
            '{"contradiction": false, "explanation": "consistent"}\n'
            "```\nEnd of output."
        )
        assert parse_json_response(text) == {
            "contradiction": False,
            "explanation": "consistent",
        }

    def test_list_json(self) -> None:
        """A bare JSON array parses (keyword-style responses)."""
        assert parse_json_response('["alpha", "beta"]') == ["alpha", "beta"]

    def test_true_failure_raises(self) -> None:
        """Totally non-JSON content raises JSONDecodeError (callers decide)."""
        with pytest.raises(json.JSONDecodeError):
            parse_json_response("this is not json at all")

    def test_none_raises(self) -> None:
        """None content raises JSONDecodeError (callers guard for None)."""
        with pytest.raises(json.JSONDecodeError):
            parse_json_response(None)

    # -- issue #533: text-level repair of illegal values INSIDE the JSON ----

    def test_bare_identifier_value_becomes_null(self) -> None:
        """``{"score": wiggle}`` parses with ``score=None`` (no total failure)."""
        assert parse_json_response('{"score": wiggle}') == {"score": None}

    def test_trailing_comma_repaired(self) -> None:
        assert parse_json_response('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}

    def test_single_quotes_repaired(self) -> None:
        assert parse_json_response("{'score': 'high'}") == {"score": "high"}

    def test_fenced_json_with_trailing_comma_repaired(self) -> None:
        text = '```json\n{"a": 1,}\n```'
        assert parse_json_response(text) == {"a": 1}

    def test_nan_repaired_to_null(self) -> None:
        assert parse_json_response('{"score": NaN}') == {"score": None}

    def test_infinity_repaired_to_null(self) -> None:
        assert parse_json_response('{"score": -Infinity}') == {"score": None}

    def test_plus_number_sign_normalised(self) -> None:
        assert parse_json_response('{"a": +5}') == {"a": 5}

    def test_bare_percentage_quoted(self) -> None:
        assert parse_json_response('{"score": 30%}') == {"score": "30%"}

    def test_bare_key_repaired(self) -> None:
        assert parse_json_response("{score: 1}") == {"score": 1}

    def test_valid_literals_are_preserved(self) -> None:
        """The bare-value repair must not clobber true/false/null."""
        assert parse_json_response('{"a": true, "b": false, "c": null}') == {
            "a": True,
            "b": False,
            "c": None,
        }

    def test_unrepairable_still_raises_jsondecodeerror(self) -> None:
        """Genuinely broken JSON still raises the same exception type."""
        with pytest.raises(json.JSONDecodeError):
            parse_json_response('{"score": wiggle some words beside')

    def test_unrepairable_brace_payload_still_raises(self) -> None:
        """A ``{...}`` payload that survives no repair still fails cleanly.

        Exercises the strategy-3 candidate loop's except/continue branch:
        the brace-match candidate is tried, fails both the direct and the
        repaired variant, and the function falls through to its final raise.
        """
        with pytest.raises(json.JSONDecodeError, match="Failed to parse"):
            parse_json_response("prose {not json at all} prose")


# ===================================================================
# salvage_fields
# ===================================================================


class TestSalvageFields:
    """Field-level schema convergence after parsing."""

    def test_lossless_numeric_string_with_unit_is_converted(self) -> None:
        payload = {"score": "30%", "name": "x"}
        out, invalid = salvage_fields(payload, {"score": float, "name": str})
        assert out["score"] == 30.0
        assert invalid == []
        # The caller's payload is not mutated.
        assert payload["score"] == "30%"

    def test_numeric_string_without_unit_is_converted(self) -> None:
        out, invalid = salvage_fields({"a": "42", "b": "3.5"}, {"a": int, "b": float})
        assert out["a"] == 42
        assert out["b"] == 3.5
        assert invalid == []

    def test_int_to_float_is_lossless(self) -> None:
        out, invalid = salvage_fields({"a": 3}, {"a": float})
        assert out["a"] == 3.0
        assert invalid == []

    def test_integral_float_to_int_is_lossless(self) -> None:
        out, invalid = salvage_fields({"a": 4.0}, {"a": int})
        assert out["a"] == 4
        assert invalid == []

    def test_non_integral_float_to_int_is_invalid(self) -> None:
        out, invalid = salvage_fields({"a": 3.5}, {"a": int})
        assert out["a"] is None
        assert invalid == ["a"]

    def test_unconvertible_value_is_nulled_and_flagged(self) -> None:
        out, invalid = salvage_fields({"score": "wiggle", "n": 3}, {"score": float, "n": int})
        assert out["score"] is None
        assert out["n"] == 3
        assert invalid == ["score"]

    def test_bool_is_not_coerced_into_number(self) -> None:
        out, invalid = salvage_fields({"a": True}, {"a": float})
        assert out["a"] is None
        assert invalid == ["a"]

    def test_missing_required_field_is_nulled_and_flagged(self) -> None:
        out, invalid = salvage_fields({}, {"score": float})
        assert out["score"] is None
        assert invalid == ["score"]

    def test_no_schema_is_a_noop(self) -> None:
        payload = {"a": 1, "b": "two"}
        out, invalid = salvage_fields(payload)
        assert out == payload
        assert invalid == []

    def test_non_dict_payload_raises_typeerror(self) -> None:
        with pytest.raises(TypeError):
            salvage_fields(["not", "a", "dict"])  # type: ignore[arg-type]

    @pytest.mark.parametrize("raw", ["%", " , ", "   "])
    def test_numeric_string_without_digits_is_invalid(self, raw: str) -> None:
        """A numeric-looking string with no digits cannot become a float."""
        out, invalid = salvage_fields({"a": raw}, {"a": float})
        assert out["a"] is None
        assert invalid == ["a"]

    def test_explicit_null_value_stays_valid(self) -> None:
        """An explicit JSON ``null`` is honest data — kept, never flagged."""
        out, invalid = salvage_fields({"a": None, "b": 1}, {"a": float, "b": int})
        assert out["a"] is None
        assert out["b"] == 1
        assert invalid == []

    def test_bool_expected_accepts_bool_only(self) -> None:
        out, invalid = salvage_fields({"a": True, "b": 1}, {"a": bool, "b": bool})
        assert out["a"] is True
        assert out["b"] is None
        assert invalid == ["b"]

    def test_bool_to_str_is_word_form(self) -> None:
        out, invalid = salvage_fields({"a": True, "b": False}, {"a": str, "b": str})
        assert out["a"] == "true"
        assert out["b"] == "false"
        assert invalid == []

    def test_float_value_passthrough(self) -> None:
        out, invalid = salvage_fields({"a": 2.5}, {"a": float})
        assert out["a"] == 2.5
        assert invalid == []

    def test_numeric_string_non_integral_to_int_is_invalid(self) -> None:
        out, invalid = salvage_fields({"a": "3.5"}, {"a": int})
        assert out["a"] is None
        assert invalid == ["a"]

    def test_number_to_str_is_stringified(self) -> None:
        out, invalid = salvage_fields({"a": 7, "b": 2.5}, {"a": str, "b": str})
        assert out["a"] == "7"
        assert out["b"] == "2.5"
        assert invalid == []

    def test_container_to_str_is_invalid(self) -> None:
        out, invalid = salvage_fields({"a": [1], "b": {"x": 1}}, {"a": str, "b": str})
        assert out["a"] is None
        assert out["b"] is None
        assert invalid == ["a", "b"]

    def test_list_expected_accepts_list_and_tuple(self) -> None:
        out, invalid = salvage_fields({"a": [1, 2], "b": (3, 4)}, {"a": list, "b": list})
        assert out["a"] == [1, 2]
        assert out["b"] == [3, 4]
        assert isinstance(out["b"], list)
        assert invalid == []

    def test_list_expected_rejects_scalar(self) -> None:
        out, invalid = salvage_fields({"a": "x"}, {"a": list})
        assert out["a"] is None
        assert invalid == ["a"]

    def test_dict_expected_accepts_dict_rejects_scalar(self) -> None:
        out, invalid = salvage_fields({"a": {"x": 1}, "b": 5}, {"a": dict, "b": dict})
        assert out["a"] == {"x": 1}
        assert out["b"] is None
        assert invalid == ["b"]

    def test_generic_expected_type_isinstance_check(self) -> None:
        out, invalid = salvage_fields({"a": (1, 2), "b": 5}, {"a": tuple, "b": tuple})
        assert out["a"] == (1, 2)
        assert out["b"] is None
        assert invalid == ["b"]


# ===================================================================
# repair_json_once
# ===================================================================


class TestRepairJsonOnce:
    """One-shot model re-emission of a malformed JSON response."""

    def test_success_calls_llm_exactly_once(self) -> None:
        calls: list[str] = []

        def llm(prompt: str) -> str:
            calls.append(prompt)
            return '{"score": 42}'

        error = json.JSONDecodeError("Expecting value", '{"score": wiggle}', 10)
        result = repair_json_once('{"score": wiggle}', error=error, llm_call=llm)

        assert result == {"score": 42}
        assert len(calls) == 1
        assert "JSON" in calls[0]
        assert '{"score": wiggle}' in calls[0]

    def test_second_bad_response_raises_with_field_name(self) -> None:
        def llm(prompt: str) -> str:
            return "still not json"

        error = json.JSONDecodeError("Expecting value [field: score]", '{"score": wiggle}', 10)
        with pytest.raises(json.JSONDecodeError) as excinfo:
            repair_json_once('{"score": wiggle}', error=error, llm_call=llm)

        assert "score" in str(excinfo.value)

    def test_llm_call_failure_preserves_jsondecodeerror_type(self) -> None:
        def llm(prompt: str) -> str:
            raise RuntimeError("gateway down")

        error = json.JSONDecodeError("Expecting value [field: score]", '{"score": wiggle}', 10)
        with pytest.raises(json.JSONDecodeError) as excinfo:
            repair_json_once('{"score": wiggle}', error=error, llm_call=llm)

        assert "score" in str(excinfo.value)
        assert "gateway down" in str(excinfo.value)

    def test_non_jsondecodeerror_error_is_reraised_with_note(self) -> None:
        """Non-JSONDecodeError failures keep their type and gain a note."""
        original = ValueError("original parse boom")

        def llm(prompt: str) -> str:
            raise RuntimeError("gateway down")

        with pytest.raises(ValueError) as excinfo:
            repair_json_once('{"score": wiggle}', error=original, llm_call=llm)

        assert excinfo.value is original
        notes = getattr(original, "__notes__", [])
        assert any("repair_json_once failed" in note for note in notes)


# ===================================================================
# call_with_fallback — reasoning-model json_mode
# ===================================================================


class TestCallWithFallbackReasoningJsonMode:
    """json_mode + reasoning_model must not send ``response_format``."""

    def _call(self, **kwargs) -> MagicMock:
        mock_litellm = _mock_litellm(json.dumps({"contradiction": False}))
        with patch.object(LLMExtractor, "_get_litellm", return_value=mock_litellm):
            response = call_with_fallback(
                messages=[{"role": "user", "content": "hi"}],
                **kwargs,
            )
        return mock_litellm, response

    def test_reasoning_model_suppresses_response_format(self) -> None:
        """json_mode=True + reasoning_model=True -> no response_format kwarg."""
        mock_litellm, response = self._call(json_mode=True, reasoning_model=True)
        call_kwargs = mock_litellm.completion.call_args.kwargs
        assert "response_format" not in call_kwargs
        # The returned content is still parseable JSON.
        content: str = response.choices[0].message.content
        assert parse_json_response(content) == {"contradiction": False}

    def test_json_mode_alone_keeps_response_format(self) -> None:
        """json_mode=True + reasoning_model=False keeps response_format."""
        mock_litellm, _ = self._call(json_mode=True, reasoning_model=False)
        assert mock_litellm.completion.call_args.kwargs["response_format"] == {
            "type": "json_object",
        }

    def test_config_reasoning_model_inherited(self) -> None:
        """reasoning_model unset inherits config.llm.reasoning_model."""
        config = Config(llm=LLMConfig(reasoning_model=True))
        mock_litellm, _ = self._call(json_mode=True, config=config)
        assert "response_format" not in mock_litellm.completion.call_args.kwargs

    def test_default_config_unchanged(self) -> None:
        """Default config (json_mode=False) sends no response_format."""
        mock_litellm, _ = self._call(json_mode=False)
        assert "response_format" not in mock_litellm.completion.call_args.kwargs


# ===================================================================
# call_with_fallback — task-level max_tokens wiring
# ===================================================================


class TestCallWithFallbackMaxTokens:
    """``LLMTaskConfig.max_tokens`` must reach the request payload."""

    def _call(self, **kwargs) -> MagicMock:
        mock_litellm = _mock_litellm(json.dumps({"a": 1}))
        with patch.object(LLMExtractor, "_get_litellm", return_value=mock_litellm):
            call_with_fallback(
                messages=[{"role": "user", "content": "hi"}],
                **kwargs,
            )
        return mock_litellm

    def test_default_stays_2000(
        self, monkeypatch: pytest.MonkeyPatch, hermetic_default_config: str
    ) -> None:
        """No ``max_tokens`` in config / no explicit value -> 2000 default.

        Hermetic: the usage-site ``autoinfo.llm.get_config_path`` seam is
        redirected to a test-owned tmp config (``hermetic_default_config``)
        that omits ``llm.max_tokens`` — the real gitignored
        ``.autoinfo/config.yaml`` (``max_tokens: 4000``) can no longer leak
        in, so this asserts the library default rather than local deployment
        state (T4, 2026-09-11).
        """
        get_config_path = MagicMock(return_value=hermetic_default_config)
        monkeypatch.setattr("autoinfo.llm.get_config_path", get_config_path)
        mock_litellm = self._call()
        assert get_config_path.called  # usage-site seam used; real config skipped
        assert mock_litellm.completion.call_args.kwargs["max_tokens"] == 2000

    def test_llm_config_max_tokens_effective(self) -> None:
        """``llm.max_tokens`` in the config reaches the request payload."""
        config = Config(llm=LLMConfig(max_tokens=1500))
        mock_litellm = self._call(config=config)
        assert mock_litellm.completion.call_args.kwargs["max_tokens"] == 1500

    def test_explicit_param_wins_over_config(self) -> None:
        """An explicit max_tokens param overrides the config value."""
        config = Config(llm=LLMConfig(max_tokens=1500))
        mock_litellm = self._call(max_tokens=300, config=config)
        assert mock_litellm.completion.call_args.kwargs["max_tokens"] == 300

    def test_task_level_override_reaches_payload(self) -> None:
        """A task-level max_tokens overrides base config in the resolved LLMConfig."""
        config = Config(
            llm=LLMConfig(
                model="deepseek/deepseek-chat",
                max_tokens=1500,
                tasks={"extraction": LLMTaskConfig(max_tokens=777)},
            )
        )
        task_cfg = _resolve_task_llm_config(config, "extraction")
        assert task_cfg.max_tokens == 777
        mock_litellm = self._call(config=Config(llm=task_cfg))
        assert mock_litellm.completion.call_args.kwargs["max_tokens"] == 777


# ===================================================================
# G4 / G5 — markdown-fenced LLM output
# ===================================================================


class TestGatesFencedJson:
    """Gates must parse markdown-fenced JSON instead of raising."""

    def test_g4_fenced_json_passes(
        self, sample_item: Item, sample_extraction: ExtractionResult
    ) -> None:
        """G4 with fenced JSON: previously raised, now passes cleanly."""
        fenced = '```json\n{"contradiction": false, "explanation": "consistent"}\n```'
        with patch.object(LLMExtractor, "_get_litellm", return_value=_mock_litellm(fenced)):
            result = G4FactualConsistency(model="test/test", json_mode=False).check(
                sample_item, sample_extraction
            )
        assert result.passed is True
        assert result.flagged is False
        assert result.details["explanation"] == "consistent"

    def test_g5_fenced_json_passes(
        self, sample_item: Item, sample_extraction: ExtractionResult
    ) -> None:
        """G5 with fenced JSON: previously raised, now passes cleanly."""
        fenced = '```json\n{"faithful": true, "explanation": "ok", "issues": []}\n```'
        sample_extraction.custom_fields = {"translation": "IVF success rates rise"}
        with patch.object(LLMExtractor, "_get_litellm", return_value=_mock_litellm(fenced)):
            result = G5TranslationAccuracy(model="test/test", json_mode=False).check(
                sample_item, sample_extraction
            )
        assert result.passed is True
        assert result.flagged is False
        assert result.details["faithful"] is True


# ===================================================================
# CEFR — max_tokens change must not regress classification
# ===================================================================


class TestCefrMaxTokens:
    """CEFR still classifies after the max_tokens bump."""

    def test_classify_with_fake_llm(self) -> None:
        """Fake LLM returning a bare level still classifies (B2)."""
        mock_litellm = _mock_litellm("B2")
        with patch.object(LLMExtractor, "_get_litellm", return_value=mock_litellm):
            result = classify_text(
                "The mitochondria is the powerhouse of the cell",
                lang="en",
                model_config={"model": "test/test"},
            )
        assert result["cefr_level"] == "B2"
        # The bump from 50 must have taken effect (and be sane).
        assert mock_litellm.completion.call_args.kwargs["max_tokens"] >= 256
