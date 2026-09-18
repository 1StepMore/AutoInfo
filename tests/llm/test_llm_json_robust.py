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
from autoinfo.llm import LLMExtractor, call_with_fallback, parse_json_response
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
