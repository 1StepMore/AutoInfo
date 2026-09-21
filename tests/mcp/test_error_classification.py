"""Issue #364: expected failures map to semantic MCP error codes.

Covers ``_classify_exception`` type mapping, ``_error_from_exc``
classification for a missing config, and the handler-level behaviour of
``_handle_list_domains`` / ``_handle_list_projects`` /
``_handle_activate_domain`` with and without a project config.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import httpx
import pytest

from autoinfo.config import ConfigNotFoundError
from autoinfo.kb import DirectorOnlyError
from autoinfo.mcp.errors import ErrorCode
from autoinfo.mcp.server import (
    _classify_exception,
    _error_from_exc,
    _handle_activate_domain,
    _handle_deactivate_domain,
    _handle_get_domain_config,
    _handle_list_domains,
    _handle_list_projects,
)

SAMPLE_CONFIG_YAML = """
project:
  name: Test Project
  created_at: '2026-07-01'
llm:
  provider: openrouter
  model: deepseek/deepseek-chat
  api_key: test-key
domains:
  - name: medical-research
    active: true
    sources: []
    topics: []
"""


@pytest.fixture
def no_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AUTOINFO_CONFIG_DIR", raising=False)
    monkeypatch.delenv("AUTOINFO_HOME", raising=False)
    return tmp_path


@pytest.fixture
def initialized_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(SAMPLE_CONFIG_YAML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AUTOINFO_CONFIG_DIR", raising=False)
    monkeypatch.delenv("AUTOINFO_HOME", raising=False)
    return tmp_path


class TestClassifyException:
    def test_director_only(self) -> None:
        assert (
            _classify_exception(DirectorOnlyError(actor="x", entry_id="e", operation="demote"))
            == ErrorCode.DIRECTOR_ONLY
        )

    def test_config_not_found(self) -> None:
        assert _classify_exception(ConfigNotFoundError("missing")) == ErrorCode.CONFIG_NOT_FOUND

    def test_generic_file_not_found(self) -> None:
        assert _classify_exception(FileNotFoundError("missing")) == ErrorCode.NOT_FOUND

    def test_value_error(self) -> None:
        assert _classify_exception(ValueError("bad input")) == ErrorCode.VALIDATION_ERROR

    def test_key_error(self) -> None:
        assert _classify_exception(KeyError("missing-key")) == ErrorCode.VALIDATION_ERROR

    def test_connection_error(self) -> None:
        assert _classify_exception(ConnectionError("refused")) == ErrorCode.TIMEOUT

    def test_httpx_connect_error(self) -> None:
        assert _classify_exception(httpx.ConnectError("refused")) == ErrorCode.TIMEOUT

    def test_unknown_exception_is_internal(self) -> None:
        assert _classify_exception(RuntimeError("boom")) == ErrorCode.INTERNAL_ERROR

    def test_litellm_authentication_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_litellm = types.ModuleType("litellm")
        fake_exceptions = types.ModuleType("litellm.exceptions")

        class AuthenticationError(Exception):
            pass

        fake_exceptions.AuthenticationError = AuthenticationError  # type: ignore[attr-defined]
        fake_litellm.exceptions = fake_exceptions  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "litellm", fake_litellm)
        monkeypatch.setitem(sys.modules, "litellm.exceptions", fake_exceptions)

        assert _classify_exception(AuthenticationError("bad key")) == ErrorCode.LLM_NOT_CONFIGURED


class TestErrorFromExcClassification:
    def test_config_not_found_is_classified(self) -> None:
        result = _error_from_exc(ConfigNotFoundError("missing"), "load config")
        assert result["error"]["code"] == "ConfigNotFound"

    def test_unknown_exception_stays_internal(self) -> None:
        result = _error_from_exc(RuntimeError("boom"), "load config")
        assert result["error"]["code"] == "InternalError"

    def test_explicit_code_is_honoured(self) -> None:
        result = _error_from_exc(ValueError("bad"), "load config", code=ErrorCode.DOMAIN_NOT_FOUND)
        assert result["error"]["code"] == "DomainNotFound"

    def test_explicit_internal_error_is_classified(self) -> None:
        result = _error_from_exc(ValueError("bad"), "load config", code=ErrorCode.INTERNAL_ERROR)
        assert result["error"]["code"] == "ValidationError"


class TestHandlersWithoutConfig:
    def test_list_domains_config_not_found(self, no_config_dir: Path) -> None:
        result = _handle_list_domains()
        assert result["success"] is False
        assert result["error"]["code"] == "ConfigNotFound"

    def test_list_projects_config_not_found(self, no_config_dir: Path) -> None:
        result = _handle_list_projects()
        assert result["success"] is False
        assert result["error"]["code"] == "ConfigNotFound"

    def test_activate_unknown_domain_config_not_found(self, no_config_dir: Path) -> None:
        result = _handle_activate_domain("nope")
        assert result["success"] is False
        assert result["error"]["code"] == "ConfigNotFound"

    def test_deactivate_unknown_domain_config_not_found(self, no_config_dir: Path) -> None:
        result = _handle_deactivate_domain("nope")
        assert result["success"] is False
        assert result["error"]["code"] == "ConfigNotFound"

    def test_get_domain_config_config_not_found(self, no_config_dir: Path) -> None:
        result = _handle_get_domain_config("nope")
        assert result["success"] is False
        assert result["error"]["code"] == "ConfigNotFound"


class TestHandlersWithConfig:
    def test_activate_unknown_domain_is_domain_not_found(self, initialized_config: Path) -> None:
        result = _handle_activate_domain("nope")
        assert result["success"] is False
        assert result["error"]["code"] == "DomainNotFound"

    def test_list_domains_succeeds(self, initialized_config: Path) -> None:
        result = _handle_list_domains()
        assert result["count"] == 1
        assert result["domains"][0]["name"] == "medical-research"
