"""Failure-injection tests for the mimo-v2.5 fallback chain (todo 2).

Unit (mandatory): monkeypatches the provider-call seam inside
``call_with_fallback`` — the per-provider ``_litellm.completion`` call
resolved via ``LLMExtractor._get_litellm`` (the same seam todo 1's
test_rate_limit_429.py uses).  The PRIMARY model raises a retryable HTTP
429 every attempt; the chain must exhaust the primary and walk through to
the configured fallback, and the fallback completion call must carry
model ``openai/mimo-v2.5`` on the opencode gateway with no key of its own
(the gateway inherits the primary key).  Zero real sleeps (``time.sleep``
patched), zero network — fully deterministic.

Hermetic config (T4, 2026-09-11): the unit tests load a **temporary config
fixture they write themselves** (``deployment_config``) instead of the
repo-root gitignored ``.autoinfo/config.yaml``.  That real deployment config
drifted to 3 fallbacks (glm-4.7-flash / nvidia-… / agnes-2.5-flash) and a
different primary, so asserting against it made the chain test fail purely
on local environment state.  A test-owned fixture keeps the injection
contract independent of the developer's config (see `tests/TRIAGE.md:206-215`
for the usage-site seam pattern).

Integration (optional): with a real key AND the real gitignored config
present, the configured chain is exercised end-to-end against the opencode
gateway.  Skipped cleanly (exit 0) otherwise.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autoinfo.config import Config, load_config
from autoinfo.llm import LLMExtractor, call_with_fallback

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / ".autoinfo" / "config.yaml"

OPENGATE_BASE_URL = "https://opencode.ai/zen/go/v1"
FALLBACK_MODEL = "mimo-v2.5"

# Test-owned deployment chain stand-in — mirrors the documented config
# (primary on the opencode gateway + exactly one mimo-v2.5 fallback on the
# same gateway with no key of its own).  Written to a tmp dir by the
# ``deployment_config`` fixture so the unit tests never read the real
# gitignored ``.autoinfo/config.yaml`` (T4, 2026-09-11).
_DEPLOYMENT_CONFIG_YAML = (
    "llm:\n"
    "  provider: openai\n"
    "  model: deepseek-v4-flash\n"
    f"  base_url: {OPENGATE_BASE_URL}\n"
    "  reasoning_model: true\n"
    "  fallback:\n"
    "    - provider: openai\n"
    f"      model: {FALLBACK_MODEL}\n"
    f"      base_url: {OPENGATE_BASE_URL}\n"
    "      api_key: ''\n"
)


class StubRateLimitError(RuntimeError):
    """Minimal LiteLLM 429 stand-in — retryable via ``status_code``."""

    def __init__(self, message: str = "Rate limit hit") -> None:
        self.status_code = 429
        super().__init__(message)


def _ok_response() -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content="ok"))])


@pytest.fixture
def deployment_config(tmp_path: Path) -> Config:
    """Load a test-owned chain config — never the repo-root real config.

    Hermetic seam for the unit tests: the chain is asserted against a
    fixture the test itself controls, so it cannot drift with the
    developer's gitignored ``.autoinfo/config.yaml`` (T4, 2026-09-11).
    """
    config_path = tmp_path / ".autoinfo" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_DEPLOYMENT_CONFIG_YAML, encoding="utf-8")
    return load_config(config_path)


class TestFallbackInjection:
    """Primary 429 -> chain falls through to mimo-v2.5 fallback."""

    def test_primary_429_falls_through_to_mimo_fallback(self, deployment_config: Config) -> None:
        cfg = deployment_config
        assert len(cfg.llm.fallback) == 1  # hermetic guard: one fallback

        primary_model = cfg.llm.resolve_model()
        fallback_model = f"{cfg.llm.fallback[0].provider or cfg.llm.provider}/{FALLBACK_MODEL}"

        called: list[dict[str, object]] = []

        def stub_completion(**kwargs: object) -> MagicMock:
            called.append(kwargs)
            model = str(kwargs["model"])
            if model == primary_model:
                raise StubRateLimitError("primary rate limited (429)")
            if model == fallback_model:
                return _ok_response()
            raise AssertionError(f"unexpected model in chain: {model}")

        mock_lm = MagicMock()
        mock_lm.completion.side_effect = stub_completion

        with (
            patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm),
            patch("time.sleep", return_value=None),  # deterministic, no sleeps
        ):
            resp = call_with_fallback(
                messages=[{"role": "user", "content": "short test"}],
                config=cfg,
                max_tokens=64,
            )

        models_called = [str(kw["model"]) for kw in called]
        # Primary exhausted its MAX_LLM_ATTEMPTS retries (3 tries), then the
        # fallback was attempted once and won.
        assert models_called.count(primary_model) == 3
        assert models_called[-1] == fallback_model
        assert resp.choices[0].message.content == "ok"

        # The fallback call carries the opencode gateway and no key of its
        # own — the gateway inherits the primary key.
        fallback_kwargs = called[-1]
        assert fallback_kwargs["api_base"] == OPENGATE_BASE_URL
        assert fallback_kwargs["api_key"] is None
        # Reasoned primary still suppresses response_format (issue #178)
        # and sends the disable-thinking body — the fallback is a reasoning
        # model on the same gateway, so the same controls apply.
        assert "response_format" not in fallback_kwargs

    def test_primary_ok_never_calls_fallback(self, deployment_config: Config) -> None:
        """When the primary succeeds no fallback is invoked."""
        cfg = deployment_config
        primary_model = cfg.llm.resolve_model()

        called: list[dict[str, object]] = []

        def stub_completion(**kwargs: object) -> MagicMock:
            called.append(kwargs)
            return _ok_response()

        mock_lm = MagicMock()
        mock_lm.completion.side_effect = stub_completion

        with (
            patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm),
            patch("time.sleep", return_value=None),
        ):
            resp = call_with_fallback(
                messages=[{"role": "user", "content": "short test"}],
                config=cfg,
                max_tokens=64,
            )

        assert [str(kw["model"]) for kw in called] == [primary_model]
        assert resp.choices[0].message.content == "ok"


@pytest.mark.skipif(
    not (os.environ.get("AUTOINFO_LLM_API_KEY") and CONFIG_PATH.is_file()),
    reason=(
        "AUTOINFO_LLM_API_KEY not set or .autoinfo/config.yaml absent — "
        "deployment-config integration variant skipped (clean skip, exit 0)"
    ),
)
def test_integration_real_chain_with_key() -> None:
    """End-to-end smoke of the real configured chain against the gateway.

    Integration only: unlike the hermetic unit tests above, this test reads
    the real gitignored ``.autoinfo/config.yaml`` and the real provider call.
    Skipped unless both the API key and the config file are present.
    """
    cfg = load_config(CONFIG_PATH)
    resp = call_with_fallback(
        messages=[
            {"role": "system", "content": "Reply with the single word: ok"},
            {"role": "user", "content": "ping"},
        ],
        config=cfg,
        max_tokens=16,
    )
    assert resp.choices[0].message.content
