"""Tests for autoinfo.translation_qa config resolvers.

Issue #195 behavior: an unconfigured deployment must raise
``JudgmentModelNotConfiguredError`` loudly instead of silently calling a
hardcoded vendor default.

- ``_resolve_timeout`` — llm.timeout from config, default, broken config
- ``_resolve_default_model`` — configured / unconfigured / resolution errors
- ``_resolve_model_pool`` — explicit pool, config-built pool with
  provider-qualified bare models, fallback entries, dedup

Tests patch ``autoinfo.config.get_config_path`` so they are hermetic
regardless of $PWD/.autoinfo or ~/.autoinfo config files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autoinfo.config import JudgmentModelNotConfiguredError
from autoinfo.translation_qa import (
    _resolve_default_model,
    _resolve_model_pool,
    _resolve_timeout,
)

_CONFIG_YAML = """
llm:
  provider: openai
  model: test-primary-model
  base_url: https://gw.test/v1
  timeout: 33.5
"""


def _write_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str = _CONFIG_YAML
) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(text, encoding="utf-8")
    monkeypatch.setattr("autoinfo.config.get_config_path", lambda: cfg)
    return cfg


def _unconfigure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("autoinfo.config.get_config_path", lambda: None)


# ---------------------------------------------------------------------------
# _resolve_timeout
# ---------------------------------------------------------------------------


class TestResolveTimeout:
    def test_timeout_from_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_config(tmp_path, monkeypatch, _CONFIG_YAML)
        assert _resolve_timeout() == 33.5

    def test_no_config_uses_llmconfig_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _unconfigure(monkeypatch)
        assert _resolve_timeout() == 120.0

    def test_unloadable_config_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = tmp_path / "does-not-exist.yaml"
        monkeypatch.setattr("autoinfo.config.get_config_path", lambda: missing)
        assert _resolve_timeout() is None


# ---------------------------------------------------------------------------
# _resolve_default_model
# ---------------------------------------------------------------------------


class TestResolveDefaultModel:
    def test_configured_model_is_returned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, monkeypatch)
        assert _resolve_default_model() == "openai/test-primary-model"

    def test_judgment_model_is_honored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(
            tmp_path,
            monkeypatch,
            _CONFIG_YAML.replace("  timeout: 33.5", "  judgment_model: test/judge-model"),
        )
        assert _resolve_default_model() == "test/judge-model"

    def test_unloadable_config_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = tmp_path / "does-not-exist.yaml"
        monkeypatch.setattr("autoinfo.config.get_config_path", lambda: missing)
        with pytest.raises(JudgmentModelNotConfiguredError):
            _resolve_default_model()

    def test_unconfigured_raises_loudly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _unconfigure(monkeypatch)
        with pytest.raises(JudgmentModelNotConfiguredError):
            _resolve_default_model()

    def test_resolution_error_is_wrapped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _unconfigure(monkeypatch)

        def _boom(_llm: object) -> str:
            raise ValueError("bad model spec")

        monkeypatch.setattr("autoinfo.config.resolve_llm_model", _boom)
        with pytest.raises(JudgmentModelNotConfiguredError, match="bad model spec"):
            _resolve_default_model()


# ---------------------------------------------------------------------------
# _resolve_model_pool
# ---------------------------------------------------------------------------


class TestResolveModelPool:
    def test_explicit_pool_returned_with_empty_strings_filtered(self) -> None:
        pool = ["test/model-a", "", "test/model-b"]
        assert _resolve_model_pool(pool) == ["test/model-a", "test/model-b"]

    def test_empty_list_falls_through_to_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, monkeypatch)
        assert _resolve_model_pool([]) == ["openai/test-primary-model"]

    def test_config_pool_qualifies_bare_model_with_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, monkeypatch)
        assert _resolve_model_pool(None) == ["openai/test-primary-model"]

    def test_config_pool_keeps_already_qualified_model(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(
            tmp_path,
            monkeypatch,
            _CONFIG_YAML.replace("model: test-primary-model", "model: openai/qualified-model"),
        )
        assert _resolve_model_pool(None) == ["openai/qualified-model"]

    def test_fallback_entries_are_appended_and_deduped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(
            tmp_path,
            monkeypatch,
            _CONFIG_YAML
            + (
                "  fallback:\n"
                "    - provider: ''\n"
                "      model: test-fallback-model\n"
                "      api_key: ''\n"
                "    - provider: openai\n"
                "      model: test-primary-model\n"
                "      api_key: ''\n"
            ),
        )
        pool = _resolve_model_pool(None)
        assert pool == ["openai/test-primary-model", "openai/test-fallback-model"]

    def test_judgment_model_bare_name_gets_provider_prefixed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(
            tmp_path,
            monkeypatch,
            _CONFIG_YAML.replace("  timeout: 33.5", "  judgment_model: bare-judge-model"),
        )
        assert _resolve_model_pool(None) == ["openai/bare-judge-model"]

    def test_unconfigured_pool_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _unconfigure(monkeypatch)
        with pytest.raises(JudgmentModelNotConfiguredError):
            _resolve_model_pool(None)
