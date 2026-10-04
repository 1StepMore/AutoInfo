"""Config-parsing tests for the LLM fallback chain (hermetic, issue #448).

These assertions used to run against the repository's real ``.autoinfo/config.yaml``
-- the gitignored per-machine deployment artifact -- and to pin *its* values
(one specific primary model, one specific fallback model, one specific
gateway). That made the module untestable in both directions: on a CI fresh
checkout the config does not exist, so a module-level ``pytestmark skipif``
skipped all three tests (nothing was measured), and on any machine whose
deployment pointed at a different gateway all three failed for reasons that had
nothing to do with the code under test. The three permanent failures sat in the
known-red budget (``tests/TRIAGE.md``) for that reason alone.

Now the config under test is **written by the test** into ``tmp_path``, so the
parse contract is measured deterministically everywhere. The values are
deliberately synthetic (``.invalid`` hosts, RFC 2606 reserved, plus model names
that exist nowhere): if the loader ever read anything other than the file
handed to it, these assertions could not hold.

Why there is no longer a "real deployment" layer here: the only assertions left
for it would be invariants ("every fallback entry carries a non-empty
``model``/``base_url``"), and that is not an invariant of the config format --
a same-provider fallback legitimately omits ``base_url`` and inherits its
provider's default. Such a test would be vacuous where it passes and
machine-dependent where it fails, which is the exact failure mode #448 removes.
The real deployment's end-to-end chain is covered where it belongs: the opt-in
integration variant in ``tests/llm/test_fallback_injection.py``, which is gated
on the API key and the real config being present.

Structural assertions are kept, not sanded down: exactly one fallback entry, its
model/base_url parsed verbatim, and a fallback that leaves the primary untouched
while inheriting the primary's provider for model resolution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from autoinfo.config import Config, load_config

# Test-owned config values — synthetic, NOT a deployment pin. See module docstring.
PRIMARY_PROVIDER = "openai"
PRIMARY_MODEL = "hermetic-primary-model"
PRIMARY_BASE_URL = "https://primary.hermetic.invalid/v1"
FALLBACK_MODEL = "hermetic-fallback-model"
FALLBACK_BASE_URL = "https://fallback.hermetic.invalid/v1"


def _config_dict(
    *,
    fallback_model: str = FALLBACK_MODEL,
    fallback_base_url: str = FALLBACK_BASE_URL,
) -> dict[str, Any]:
    """A minimal config dict: primary llm section + exactly one fallback entry.

    The fallback entry declares ``model`` + ``base_url`` only — its empty
    provider is what makes the primary-provider inheritance observable.
    """
    return {
        "project": {"name": "hermetic-fallback-config"},
        "llm": {
            "provider": PRIMARY_PROVIDER,
            "model": PRIMARY_MODEL,
            "base_url": PRIMARY_BASE_URL,
            "fallback": [
                {"model": fallback_model, "base_url": fallback_base_url},
            ],
        },
        "domains": [],
    }


def _write_config(tmp_path: Path, name: str = "config.yaml", **overrides: str) -> Path:
    """Write a config yaml into *tmp_path* and return its path."""
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(_config_dict(**overrides), sort_keys=False),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Path of a test-owned config, plus a cwd that cannot reach the real one.

    ``monkeypatch.chdir`` is belt-and-braces: ``load_config`` is handed the
    absolute path, and chdir'ing into the tmp dir additionally makes any
    cwd-relative resolution of ``.autoinfo/config.yaml`` impossible.
    """
    monkeypatch.chdir(tmp_path)
    return _write_config(tmp_path)


@pytest.fixture
def cfg(config_path: Path) -> Config:
    """The parsed test-owned config."""
    return load_config(config_path)


def test_primary_llm_section_parsed_verbatim(config_path: Path, cfg: Config) -> None:
    """provider/model/base_url come back exactly as the file spells them."""
    assert cfg.llm.provider == PRIMARY_PROVIDER, config_path
    assert cfg.llm.model == PRIMARY_MODEL, config_path
    assert cfg.llm.base_url == PRIMARY_BASE_URL, config_path
    # A bare model name is qualified with the provider on resolve; the parsed
    # `model` field itself stays verbatim (no in-place prefixing).
    assert cfg.llm.resolve_model() == f"{PRIMARY_PROVIDER}/{PRIMARY_MODEL}", config_path


def test_single_fallback_entry_parsed_verbatim(
    config_path: Path, cfg: Config, tmp_path: Path
) -> None:
    """The chain holds exactly one entry, with its model/base_url verbatim."""
    assert len(cfg.llm.fallback) == 1, f"{config_path}: {cfg.llm.fallback}"

    fb0 = cfg.llm.fallback[0]
    assert fb0.model == FALLBACK_MODEL, config_path
    assert fb0.base_url == FALLBACK_BASE_URL, config_path
    # The entry declared no provider of its own — the loader must not invent one.
    assert fb0.provider == "", config_path

    # The parse result is bound to the file handed to ``load_config`` and to no
    # ambient state (the #448 regression lock): a second config in the same tmp
    # dir, with different values, must parse to *those* values.
    second = _write_config(
        tmp_path,
        name="second-config.yaml",
        fallback_model="hermetic-second-fallback-model",
        fallback_base_url="https://second.hermetic.invalid/v1",
    )
    second_cfg = load_config(second)
    assert len(second_cfg.llm.fallback) == 1, second
    assert second_cfg.llm.fallback[0].model == "hermetic-second-fallback-model", second
    assert second_cfg.llm.fallback[0].base_url == "https://second.hermetic.invalid/v1", second


def test_fallback_leaves_primary_untouched(config_path: Path, cfg: Config) -> None:
    """Parsing the chain mutates nothing on the primary, and the entry's empty
    provider resolves against the primary's (the call-path rule in
    ``LLMConfig.resolve_model``'s ``default_provider``)."""
    assert cfg.llm.provider == PRIMARY_PROVIDER, config_path
    assert cfg.llm.model == PRIMARY_MODEL, config_path
    assert cfg.llm.base_url == PRIMARY_BASE_URL, config_path
    assert cfg.llm.resolve_model() == f"{PRIMARY_PROVIDER}/{PRIMARY_MODEL}", config_path

    fb0 = cfg.llm.fallback[0]
    assert fb0.resolve_model(default_provider=cfg.llm.provider) == (
        f"{PRIMARY_PROVIDER}/{FALLBACK_MODEL}"
    ), config_path
    effective = f"{fb0.provider or cfg.llm.provider}/{fb0.model or cfg.llm.model}"
    assert effective == f"{PRIMARY_PROVIDER}/{FALLBACK_MODEL}", config_path
