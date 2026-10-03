"""Provider-aware thinking-disable parameter shape (regression, AMD Radeon).

The disable-thinking request parameter is not standardized: gateways spell it
differently and either hard-400 on an unrecognized body parameter or silently
ignore it.  ``autoinfo.llm`` therefore resolves the shape per gateway in one
place (:func:`autoinfo.llm.thinking_disable_body`).

Locked here:
- the DeepSeek/Anthropic-style shape is emitted byte-identically;
- the vLLM/SGLang-style ``chat_template_kwargs`` shape is emitted for mapped
  gateways;
- an unmapped provider/gateway keeps the legacy shape (no regression);
- ``disable_thinking=False`` (judgment gates) sends NO disable body and wins
  over the disable path on every gateway.

All LLM calls are mocked — no real API calls are made, no API key is needed.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from autoinfo.config import Config, LLMConfig
from autoinfo.llm import (
    DEFAULT_THINKING_SHAPE,
    THINKING_DISABLE_BODIES,
    THINKING_SHAPE_ANTHROPIC,
    THINKING_SHAPE_CHAT_TEMPLATE,
    LLMExtractor,
    call_with_fallback,
    thinking_disable_body,
)

DEEPSEEK_BASE_URL = "https://opencode.ai/zen/go/v1"
RADEON_BASE_URL = "https://developer.amd.com.cn/radeon/api/v1"


def _mock_litellm() -> MagicMock:
    mock_litellm = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"ok": True})
    mock_litellm.completion.return_value = mock_response
    return mock_litellm


def _call(
    *,
    base_url: str,
    reasoning_model: bool = True,
    disable_thinking: bool = True,
) -> MagicMock:
    """Build one ``call_with_fallback`` request payload against a mocked litellm."""
    config = Config(llm=LLMConfig(provider="openai", base_url=base_url, model="some-model"))
    mock_litellm = _mock_litellm()
    with patch.object(LLMExtractor, "_get_litellm", return_value=mock_litellm):
        call_with_fallback(
            messages=[{"role": "user", "content": "hi"}],
            reasoning_model=reasoning_model,
            disable_thinking=disable_thinking,
            config=config,
        )
    return mock_litellm


class TestThinkingDisableShape:
    """``thinking_disable_body`` — the single shape decision point."""

    def test_deepseek_gateway_keeps_anthropic_shape(self) -> None:
        """Given a DeepSeek gateway, when resolving the shape, then the
        Anthropic-style body is returned unchanged."""
        assert thinking_disable_body("openai", DEEPSEEK_BASE_URL) == {
            "thinking": {"type": "disabled"},
        }

    def test_radeon_gateway_uses_chat_template_shape(self) -> None:
        """Given the AMD Radeon gateway, when resolving the shape, then the
        vLLM/SGLang-style ``chat_template_kwargs`` body is returned."""
        assert thinking_disable_body("openai", RADEON_BASE_URL) == {
            "chat_template_kwargs": {"enable_thinking": False},
        }

    def test_unmapped_gateway_falls_back_to_default_shape(self) -> None:
        """Given a gateway in neither map, when resolving the shape, then the
        documented default (legacy) shape is returned."""
        assert DEFAULT_THINKING_SHAPE == THINKING_SHAPE_ANTHROPIC
        assert thinking_disable_body("openai", "https://api.example.com/v1") == {
            "thinking": {"type": "disabled"},
        }
        assert thinking_disable_body("openai", "") == {"thinking": {"type": "disabled"}}

    def test_registry_covers_both_shapes(self) -> None:
        """Given the shape registry, when every mapped shape is resolved, then
        each id has a distinct body."""
        assert set(THINKING_DISABLE_BODIES) == {
            THINKING_SHAPE_ANTHROPIC,
            THINKING_SHAPE_CHAT_TEMPLATE,
        }
        assert (
            THINKING_DISABLE_BODIES[THINKING_SHAPE_ANTHROPIC]
            != THINKING_DISABLE_BODIES[THINKING_SHAPE_CHAT_TEMPLATE]
        )

    def test_gateway_lookup_ignores_scheme_port_and_case(self) -> None:
        """Given a base_url with scheme/port/mixed case, when resolving the
        shape, then the host still matches the gateway map."""
        noisy = "HTTPS://user@Developer.AMD.com.cn:443/radeon/api/v1"
        assert (
            thinking_disable_body("openai", noisy)
            == THINKING_DISABLE_BODIES[THINKING_SHAPE_CHAT_TEMPLATE]
        )

    def test_returned_body_is_not_the_registry_object(self) -> None:
        """Given a resolved body, when a caller mutates it, then the registry
        is unaffected."""
        body = thinking_disable_body("openai", RADEON_BASE_URL)
        body["chat_template_kwargs"]["enable_thinking"] = True
        assert THINKING_DISABLE_BODIES[THINKING_SHAPE_CHAT_TEMPLATE] == {
            "chat_template_kwargs": {"enable_thinking": False}
        }


class TestExtraBodyOnTheWire:
    """``_completion_request`` must put the resolved shape on the wire."""

    def test_disable_body_never_uses_the_openai_sdk_kwarg_name(self) -> None:
        """Given any reasoning deployment, when the request is built, then the
        body is not sent as ``additional_body``.

        LiteLLM does not recognise that OpenAI SDK name and drops it silently,
        so the model keeps reasoning and the shared max_tokens budget is
        exhausted (finish_reason=length).  This is the exact regression that
        made reasoning-disable a no-op on every gateway."""
        for base_url in (DEEPSEEK_BASE_URL, RADEON_BASE_URL):
            mock_litellm = _call(base_url=base_url)
            assert "additional_body" not in mock_litellm.completion.call_args.kwargs
            assert mock_litellm.completion.call_args.kwargs["extra_body"]

    def test_deepseek_request_is_byte_identical(self) -> None:
        """Given a reasoning DeepSeek deployment, when the request is built,
        then ``extra_body`` is exactly the legacy ``thinking`` shape."""
        mock_litellm = _call(base_url=DEEPSEEK_BASE_URL)
        assert mock_litellm.completion.call_args.kwargs["extra_body"] == {
            "thinking": {"type": "disabled"}
        }

    def test_radeon_request_sends_chat_template_kwargs(self) -> None:
        """Given a reasoning AMD Radeon deployment, when the request is built,
        then ``chat_template_kwargs`` is sent and ``thinking`` is absent."""
        mock_litellm = _call(base_url=RADEON_BASE_URL)
        body = mock_litellm.completion.call_args.kwargs["extra_body"]
        assert body == {"chat_template_kwargs": {"enable_thinking": False}}
        assert "thinking" not in body

    def test_non_reasoning_model_sends_no_disable_body(self) -> None:
        """Given a non-reasoning deployment, when the request is built, then
        no disable body is sent at all."""
        mock_litellm = _call(base_url=RADEON_BASE_URL, reasoning_model=False)
        assert "extra_body" not in mock_litellm.completion.call_args.kwargs

    def test_judgment_gate_reenable_wins_over_disable(self) -> None:
        """Given a judgment gate on a mapped gateway, when it re-enables
        thinking, then no disable body is sent."""
        mock_litellm = _call(base_url=RADEON_BASE_URL, disable_thinking=False)
        assert "extra_body" not in mock_litellm.completion.call_args.kwargs

    def test_judgment_gate_reenable_wins_on_legacy_gateway(self) -> None:
        """Given a judgment gate on a legacy gateway, when it re-enables
        thinking, then no disable body is sent."""
        mock_litellm = _call(base_url=DEEPSEEK_BASE_URL, disable_thinking=False)
        assert "extra_body" not in mock_litellm.completion.call_args.kwargs
