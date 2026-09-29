"""Config-parsing tests for the LLM fallback chain.

Asserts that :func:`autoinfo.config.load_config` parses ``llm.fallback``
from the repository's real ``.autoinfo/config.yaml`` (the single
authorized direct config edit): the cross-endpoint ``mimo-v2.5`` fallback on
``https://opencode.ai/zen/go/v1``.  The primary provider/model must stay
untouched (``openai/deepseek/deepseek-v4.1-flash`` on the commandcode
gateway).  This is a deployment-config pin: when the authorized config
changes, these expectations move with it.

The config path is resolved relative to this test file (repo root) so the
assertions hold regardless of the current working directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autoinfo.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / ".autoinfo" / "config.yaml"

# The tests assert against the repository's real (gitignored) config — the
# single authorized direct config edit. Absent on CI (fresh checkout has no
# .autoinfo/), so skip cleanly instead of failing FileNotFoundError.
pytestmark = pytest.mark.skipif(
    not CONFIG_PATH.is_file(),
    reason=".autoinfo/config.yaml absent (gitignored) — deployment-config test",
)

PRIMARY_MODEL = "openai/deepseek/deepseek-v4.1-flash"
PRIMARY_PROVIDER = "openai"
PRIMARY_BASE_URL = "https://api.commandcode.ai/provider/v1"
FALLBACK_MODEL = "mimo-v2.5"
FALLBACK_BASE_URL = "https://opencode.ai/zen/go/v1"


def test_fallback_chain_parsed_from_real_config() -> None:
    """The loader parses the configured fallback entry verbatim."""
    cfg = load_config(CONFIG_PATH)

    assert len(cfg.llm.fallback) == 1, (
        f"expected exactly 1 fallback entry, got {len(cfg.llm.fallback)}"
    )

    # Cross-endpoint fallback: mimo-v2.5 on the opencode gateway.
    fb0 = cfg.llm.fallback[0]
    assert fb0.model == FALLBACK_MODEL
    assert fb0.base_url == FALLBACK_BASE_URL


def test_primary_unchanged() -> None:
    """openai/deepseek/deepseek-v4.1-flash stays the primary model/provider."""
    cfg = load_config(CONFIG_PATH)

    assert cfg.llm.provider == PRIMARY_PROVIDER
    assert cfg.llm.model == PRIMARY_MODEL
    assert cfg.llm.base_url == PRIMARY_BASE_URL
    assert cfg.llm.resolve_model() == PRIMARY_MODEL


def test_fallback_model_resolves_with_primary_provider() -> None:
    """Each fallback model resolves with the primary provider when provider is empty."""
    cfg = load_config(CONFIG_PATH)

    fb0 = cfg.llm.fallback[0]
    effective_provider = fb0.provider or cfg.llm.provider
    effective_model = fb0.model or cfg.llm.model
    assert f"{effective_provider}/{effective_model}" == "openai/mimo-v2.5"
