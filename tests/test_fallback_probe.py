"""Fallback-chain diagnosis for issue #605.

Two regressions are locked here:

1. ``llm_fallback_health`` must flag a fallback whose configured ``model``
   already carries the provider prefix that ``call_with_fallback`` prepends
   (``openai/openai/...``).  Configuration is reported as-is — never repaired.
2. ``probe_fallbacks`` must issue one real request per entry, return one
   result per entry, and swallow failures (no exception escapes) while never
   leaking the entry's API key in the error text.
"""

from __future__ import annotations

from typing import Any

from autoinfo import config as config_module
from autoinfo.config import Config, LLMConfig, llm_fallback_health, probe_fallbacks

PRIMARY_URL = "https://primary.example/v1"
FALLBACK_URL = "https://fallback.example/v1"
EXPLICIT_KEY = "fallback-secret-key"


def _config(fallback: list[LLMConfig]) -> Config:
    return Config(
        llm=LLMConfig(
            provider="openai",
            model="deepseek-v4.1-flash",
            api_key="primary-secret-key",
            base_url=PRIMARY_URL,
            fallback=fallback,
        )
    )


class TestDoublePrefixDetection:
    def test_double_prefixed_model_is_flagged(self) -> None:
        cfg = _config(
            [
                LLMConfig(
                    provider="openai",
                    model="openai/deepseek-v4.1-flash",
                    base_url=FALLBACK_URL,
                    api_key=EXPLICIT_KEY,
                )
            ]
        )

        health = llm_fallback_health(cfg)

        assert health["entries"][0]["double_prefix"] is True

    def test_normal_model_is_not_flagged(self) -> None:
        cfg = _config(
            [
                LLMConfig(
                    provider="openai",
                    model="deepseek-v4.1-flash",
                    base_url=FALLBACK_URL,
                    api_key=EXPLICIT_KEY,
                )
            ]
        )

        health = llm_fallback_health(cfg)

        assert health["entries"][0]["double_prefix"] is False

    def test_inherited_provider_uses_primary_provider_prefix(self) -> None:
        cfg = _config(
            [
                LLMConfig(
                    provider="",
                    model="openai/deepseek-v4.1-flash",
                    base_url=FALLBACK_URL,
                    api_key=EXPLICIT_KEY,
                )
            ]
        )

        health = llm_fallback_health(cfg)

        assert health["entries"][0]["inherits_provider"] is True
        assert health["entries"][0]["double_prefix"] is True


class TestProbeFallbacks:
    def test_success_and_failure_are_reported_without_raising(
        self, monkeypatch: Any
    ) -> None:
        cfg = _config(
            [
                LLMConfig(
                    provider="",
                    model="good-model",
                    base_url=FALLBACK_URL,
                    api_key=EXPLICIT_KEY,
                ),
                LLMConfig(
                    provider="",
                    model="bad-model",
                    base_url=FALLBACK_URL,
                    api_key=EXPLICIT_KEY,
                ),
            ]
        )
        calls: list[dict[str, Any]] = []

        def fake_completion(**kwargs: Any) -> object:
            calls.append(kwargs)
            if kwargs["model"].endswith("bad-model"):
                # Include the key so the redaction assertion is meaningful.
                raise RuntimeError(f"401 invalid api key: {kwargs['api_key']}")
            return object()

        monkeypatch.setattr(config_module, "_probe_completion", fake_completion)

        results = probe_fallbacks(cfg)

        assert len(results) == 2
        assert len(calls) == 2

        good, bad = results
        assert good["index"] == 0
        assert good["model"] == "openai/good-model"
        assert good["ok"] is True
        assert good["status"] == "ok"
        assert good["error"] is None
        assert good["latency_ms"] >= 0.0

        assert bad["index"] == 1
        assert bad["model"] == "openai/bad-model"
        assert bad["ok"] is False
        assert bad["status"] == "error"
        assert "401" in bad["error"]
        assert EXPLICIT_KEY not in bad["error"]
        assert len(bad["error"]) <= 200

    def test_probe_failure_does_not_escape(self, monkeypatch: Any) -> None:
        cfg = _config(
            [
                LLMConfig(
                    provider="",
                    model="only-model",
                    base_url=FALLBACK_URL,
                    api_key=EXPLICIT_KEY,
                )
            ]
        )

        def boom(**kwargs: Any) -> object:
            raise RuntimeError("connection refused")

        monkeypatch.setattr(config_module, "_probe_completion", boom)

        results = probe_fallbacks(cfg)

        assert len(results) == 1
        assert results[0]["ok"] is False
        assert results[0]["status"] == "error"
        assert "connection refused" in results[0]["error"]
