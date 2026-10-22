"""Single-source defaults (issue #587).

The same knob (model, TTL, timeout, KB content floor) used to carry different
values in different modules; these assertions keep the documented default and
every runtime surface on the same constant.
"""

from __future__ import annotations

from autoinfo import llm
from autoinfo.config import DEFAULT_TTL_DAYS, LLMConfig, create_default_config
from autoinfo.defaults import (
    DEFAULT_LLM_TIMEOUT,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    DEFAULT_TIMEOUT_SECONDS,
    MIN_KB_CONTENT_CHARS,
)
from autoinfo.kb import MIN_KB_CONTENT_CHARS as KB_MIN_CONTENT_CHARS


def test_llm_reuses_the_defaults_module() -> None:
    assert llm.DEFAULT_MODEL == DEFAULT_MODEL
    assert llm.DEFAULT_PROVIDER == DEFAULT_PROVIDER


def test_config_timeout_and_ttl_are_shared() -> None:
    assert DEFAULT_LLM_TIMEOUT == DEFAULT_TIMEOUT_SECONDS
    assert LLMConfig().timeout == DEFAULT_LLM_TIMEOUT
    assert DEFAULT_TTL_DAYS == 90


def test_scaffold_uses_the_documented_default_model() -> None:
    cfg = create_default_config("demo")
    assert cfg["llm"]["provider"] == DEFAULT_PROVIDER
    assert cfg["llm"]["model"] == DEFAULT_MODEL


def test_kb_content_floor_is_single_source() -> None:
    assert MIN_KB_CONTENT_CHARS == 50
    assert KB_MIN_CONTENT_CHARS == MIN_KB_CONTENT_CHARS
