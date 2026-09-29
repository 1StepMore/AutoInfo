"""Same-gateway API-key inheritance for the LLM fallback chain.

The documented contract used to promise that *any* empty fallback
``api_key`` inherits the primary key.  That was never implemented, and
implementing it unconditionally would leak one vendor's key to another
vendor's gateway.  The real rule: an empty fallback key inherits the
resolved primary key **only** when the fallback targets the same
``base_url`` as the primary.

These tests monkeypatch the LiteLLM call seam inside
``call_with_fallback`` and assert on the ``api_key`` kwarg actually passed
to ``litellm.completion`` — the real behavior, not an internal helper.
No network, no sleeps: ``_is_retryable_error`` is forced to False so each
chain entry is attempted exactly once.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.config import Config, LLMConfig
from autoinfo.llm import LLMExtractor, call_with_fallback

PRIMARY_URL = "https://api.commandcode.ai/provider/v1"
OTHER_URL = "https://opencode.ai/zen/go/v1"
PRIMARY_ENV_KEY = "primary-commandcode-key"


def _ok_response() -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content="ok"))])


def _config(
    *,
    base_url: str = PRIMARY_URL,
    api_key: str = "",
    fallback: list[LLMConfig] | None = None,
) -> Config:
    return Config(
        llm=LLMConfig(
            provider="openai",
            model="deepseek-v4.1-flash",
            base_url=base_url,
            api_key=api_key,
            fallback=fallback or [],
        )
    )


def _completion_calls(config: Config) -> list[dict[str, Any]]:
    """Drive ``call_with_fallback`` (primary fails, fallbacks win) once each."""
    primary_model = config.llm.resolve_model()
    calls: list[dict[str, Any]] = []

    def stub_completion(**kwargs: Any) -> MagicMock:
        calls.append(kwargs)
        if str(kwargs["model"]) == primary_model:
            raise RuntimeError("primary failed")
        return _ok_response()

    mock_lm = MagicMock()
    mock_lm.completion.side_effect = stub_completion
    with (
        patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm),
        patch("autoinfo.llm._is_retryable_error", return_value=False),
    ):
        call_with_fallback(
            messages=[{"role": "user", "content": "x"}], config=config, max_tokens=16
        )
    return calls


def test_same_gateway_empty_fallback_key_inherits_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(a) fallback on the primary gateway with no key -> primary key."""
    monkeypatch.setenv("AUTOINFO_LLM_API_KEY", PRIMARY_ENV_KEY)
    config = _config(
        fallback=[LLMConfig(model="mimo-v2.5", base_url=PRIMARY_URL, api_key="")],
    )

    calls = _completion_calls(config)

    assert calls[0]["api_key"] == PRIMARY_ENV_KEY
    assert calls[-1]["api_key"] == PRIMARY_ENV_KEY
    assert calls[-1]["api_base"] == PRIMARY_URL


def test_same_gateway_trailing_slash_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    """Endpoint comparison strips whitespace and a trailing slash."""
    monkeypatch.setenv("AUTOINFO_LLM_API_KEY", PRIMARY_ENV_KEY)
    config = _config(
        base_url=PRIMARY_URL,
        fallback=[LLMConfig(model="mimo-v2.5", base_url=f"  {PRIMARY_URL}/  ", api_key="")],
    )

    calls = _completion_calls(config)

    assert calls[-1]["api_key"] == PRIMARY_ENV_KEY


def test_cross_gateway_empty_fallback_key_gets_no_key(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """(b) fallback on a different gateway -> primary key must NOT leak."""
    monkeypatch.setenv("AUTOINFO_LLM_API_KEY", PRIMARY_ENV_KEY)
    config = _config(
        fallback=[LLMConfig(model="mimo-v2.5", base_url=OTHER_URL, api_key="")],
    )

    with caplog.at_level(logging.WARNING, logger="autoinfo.llm"):
        calls = _completion_calls(config)

    assert calls[0]["api_key"] == PRIMARY_ENV_KEY
    assert calls[-1]["api_key"] is None
    assert calls[-1]["api_base"] == OTHER_URL
    assert any("without an API key" in record.getMessage() for record in caplog.records)


def test_fallback_env_placeholder_is_resolved_and_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(c) an explicit ${ENV} fallback key is expanded and never overridden."""
    monkeypatch.setenv("AUTOINFO_LLM_API_KEY", PRIMARY_ENV_KEY)
    monkeypatch.setenv("FB_TEST_KEY", "fallback-secret")
    config = _config(
        fallback=[LLMConfig(model="mimo-v2.5", base_url=OTHER_URL, api_key="${FB_TEST_KEY}")],
    )

    calls = _completion_calls(config)

    assert calls[-1]["api_key"] == "fallback-secret"


def test_fallback_explicit_literal_key_wins_over_inheritance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(d) an explicit literal fallback key is used as-is on its own gateway."""
    monkeypatch.setenv("AUTOINFO_LLM_API_KEY", PRIMARY_ENV_KEY)
    config = _config(
        fallback=[LLMConfig(model="mimo-v2.5", base_url=PRIMARY_URL, api_key="literal-fb-key")],
    )

    calls = _completion_calls(config)

    assert calls[-1]["api_key"] == "literal-fb-key"


def test_primary_key_resolves_from_autoinfo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """(e) empty config.llm.api_key -> AUTOINFO_LLM_API_KEY, then inherited."""
    monkeypatch.setenv("AUTOINFO_LLM_API_KEY", PRIMARY_ENV_KEY)
    config = _config(
        api_key="",
        fallback=[LLMConfig(model="mimo-v2.5", base_url=PRIMARY_URL, api_key="")],
    )

    calls = _completion_calls(config)

    assert calls[0]["api_key"] == PRIMARY_ENV_KEY
    assert calls[-1]["api_key"] == PRIMARY_ENV_KEY


def test_fallback_without_base_url_does_not_inherit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(f) no fallback base_url -> provider default, never the primary gateway."""
    monkeypatch.setenv("AUTOINFO_LLM_API_KEY", PRIMARY_ENV_KEY)
    config = _config(
        fallback=[LLMConfig(model="mimo-v2.5", base_url="", api_key="")],
    )

    calls = _completion_calls(config)

    assert calls[-1]["api_key"] is None
