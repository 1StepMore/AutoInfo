"""Model-name normalization at the LLM candidate-construction site (#791).

A bare model name in the config (``model: spark-x2.6``) must never reach
LiteLLM alone — it is rejected with ``LLM Provider NOT provided`` and burns a
failed round-trip on every call.  A prefixed name (``openai/spark-x2.6``)
must never be re-prefixed into ``openai/openai/spark-x2.6`` — the gateway
answers ``no category route found``.  The normalization happens once, where
the candidate chain is built in :func:`autoinfo.llm.call_with_fallback`:
bare names get ``{provider}/{model}`` as the FIRST (and only) candidate,
prefixed names pass through unchanged — both for the primary and for every
fallback entry.

Zero network, zero real config: the stubbed completion seam records every
model string that would have been sent.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from autoinfo.config import load_config
from autoinfo.llm import LLMExtractor, call_with_fallback

BASE_URL = "https://gateway.example/v1"


def _ok_response() -> MagicMock:
    return MagicMock(choices=[MagicMock(message=MagicMock(content="ok"))])


def _write_config(tmp_path: Path, llm: dict[str, object]) -> object:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"llm": llm}), encoding="utf-8")
    return load_config(config_path)


def _models_sent(config: object) -> list[str]:
    called: list[dict[str, object]] = []

    def stub_completion(**kwargs: object) -> MagicMock:
        called.append(kwargs)
        return _ok_response()

    mock_lm = MagicMock()
    mock_lm.completion.side_effect = stub_completion
    with patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm):
        call_with_fallback(
            messages=[{"role": "user", "content": "hi"}],
            config=config,  # type: ignore[arg-type]
            max_tokens=16,
        )
    return [str(kw["model"]) for kw in called]


def test_bare_model_sends_only_the_prefixed_candidate(tmp_path: Path) -> None:
    """Bare config model -> the FIRST candidate is already ``{provider}/{model}``.

    The bare name itself is never attempted: LiteLLM would reject it with
    "LLM Provider NOT provided", so a bare-name candidate can only ever be a
    wasted round-trip (#791).
    """
    cfg = _write_config(
        tmp_path,
        {"provider": "openai", "model": "spark-x2.6", "base_url": BASE_URL},
    )

    models = _models_sent(cfg)

    assert models, "the primary candidate must be attempted"
    assert models[0] == "openai/spark-x2.6"
    assert "spark-x2.6" not in models, "the bare name must never be sent alone"
    assert all(m == "openai/spark-x2.6" for m in models)


def test_prefixed_model_is_never_double_prefixed(tmp_path: Path) -> None:
    """Prefixed config model -> sent exactly as configured.

    ``model: openai/spark-x2.6`` with ``provider: openai`` must not become
    ``openai/openai/spark-x2.6`` (the gateway answers "no category route
    found" to that shape).
    """
    cfg = _write_config(
        tmp_path,
        {"provider": "openai", "model": "openai/spark-x2.6", "base_url": BASE_URL},
    )

    models = _models_sent(cfg)

    assert models == ["openai/spark-x2.6"]
    assert not any(m.count("/") > 1 for m in models), "no double-prefixed candidate"


def test_prefixed_fallback_model_is_never_double_prefixed(tmp_path: Path) -> None:
    """A prefixed FALLBACK model passes through; a bare one gets the provider.

    The fallback entries used to be built with an unconditional
    ``f\"{provider}/{model}\"`` — a prefixed fallback model silently became
    a double-prefixed candidate (#791).  The primary fails so the chain
    actually walks into both fallback entries.
    """
    cfg = _write_config(
        tmp_path,
        {
            "provider": "openai",
            "model": "spark-x2.6",
            "base_url": BASE_URL,
            "fallback": [
                {"model": "openai/flash-x1", "base_url": BASE_URL},
                {"model": "flash-x2", "base_url": BASE_URL},
            ],
        },
    )

    called: list[dict[str, object]] = []

    def stub_completion(**kwargs: object) -> MagicMock:
        called.append(kwargs)
        model = str(kwargs["model"])
        if model in ("openai/spark-x2.6", "openai/flash-x1"):
            raise RuntimeError("entry down")  # non-retryable -> next entry
        return _ok_response()

    mock_lm = MagicMock()
    mock_lm.completion.side_effect = stub_completion
    with (
        patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm),
        patch("time.sleep", return_value=None),
    ):
        call_with_fallback(
            messages=[{"role": "user", "content": "hi"}],
            config=cfg,  # type: ignore[arg-type]
            max_tokens=16,
        )

    models = [str(kw["model"]) for kw in called]
    assert models == ["openai/spark-x2.6", "openai/flash-x1", "openai/flash-x2"]
    assert not any(m.count("/") > 1 for m in models)


def test_explicit_bare_model_param_is_also_normalized(tmp_path: Path) -> None:
    """An explicit bare ``model=`` argument gets the same treatment."""
    cfg = _write_config(
        tmp_path,
        {"provider": "openai", "model": "spark-x2.6", "base_url": BASE_URL},
    )

    called: list[dict[str, object]] = []

    def stub_completion(**kwargs: object) -> MagicMock:
        called.append(kwargs)
        return _ok_response()

    mock_lm = MagicMock()
    mock_lm.completion.side_effect = stub_completion
    with patch.object(LLMExtractor, "_get_litellm", return_value=mock_lm):
        call_with_fallback(
            messages=[{"role": "user", "content": "hi"}],
            model="spark-x2.6",  # bare explicit override
            config=cfg,  # type: ignore[arg-type]
            max_tokens=16,
        )

    models = [str(kw["model"]) for kw in called]
    assert models == ["openai/spark-x2.6"]
