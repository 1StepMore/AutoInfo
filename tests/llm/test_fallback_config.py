"""Config-parsing tests for the LLM fallback chain (#448).

These assertions are about the *code*, not about whichever gateway a given
machine happens to be pointed at. The previous version read the repository's
gitignored ``.autoinfo/config.yaml`` and compared it to hardcoded expected
model names, which gave two outcomes and neither was useful: skipped when the
config was absent (no coverage at all), or red on any deployment whose model
differed from the author's (a false alarm about code that was never touched).

The invariants actually enforced by the source are the inheritance rules:
``llm.provider``/``llm.model``/``llm.base_url`` are deployment choices, while
"an empty fallback provider inherits the primary" and "an empty fallback key
inherits the primary key **only** toward the same gateway" are code
guarantees. Those are asserted here against a config each test writes itself,
via the production resolver :func:`autoinfo.config.llm_fallback_health` -- not
reimplemented in the test.

The deployment-config pin is preserved as a separate opt-in check that skips
unless ``AUTOINFO_DEPLOYMENT_PIN=1``, so it can never turn a build red.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from autoinfo.config import llm_fallback_health, load_config

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT_CONFIG = REPO_ROOT / ".autoinfo" / "config.yaml"


def _keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve the ${...} references these configs use.

    Without this the primary key resolves empty and every case collapses to
    ``no_primary_key``, which would test nothing.
    """
    monkeypatch.setenv("AUTOINFO_LLM_API_KEY", "primary-secret")
    monkeypatch.setenv("OTHER_VENDOR_KEY", "other-vendor-secret")


def _write_config(tmp_path: Path, llm: dict[str, object]) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump({"llm": llm}), encoding="utf-8")
    return path


def _entry(health: dict[str, Any], index: int = 0) -> dict[str, Any]:
    entries = health["entries"]
    assert isinstance(entries, list)
    entry = entries[index]
    assert isinstance(entry, dict)
    return entry


def test_same_gateway_fallback_inherits_the_primary_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _keys(monkeypatch)
    """An empty key inherits **only** when the fallback targets the primary's base_url."""
    path = _write_config(
        tmp_path,
        {
            "provider": "openai",
            "model": "primary-model",
            "api_key": "${AUTOINFO_LLM_API_KEY}",
            "base_url": "https://gateway.example/v1",
            "fallback": [{"model": "fallback-model", "base_url": "https://gateway.example/v1"}],
        },
    )

    health = llm_fallback_health(load_config(path))

    assert health["configured"] is True
    assert health["count"] == 1
    fb = _entry(health)
    assert fb["inherits_provider"] is True, "empty provider must inherit the primary"
    assert fb["inherits_key"] is True
    assert fb["key_status"] == "inherited_same_gateway"


def test_cross_endpoint_fallback_never_inherits_the_primary_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _keys(monkeypatch)
    """One vendor's key must not reach another vendor's gateway (#410)."""
    path = _write_config(
        tmp_path,
        {
            "provider": "openai",
            "model": "primary-model",
            "api_key": "${AUTOINFO_LLM_API_KEY}",
            "base_url": "https://gateway-a.example/v1",
            "fallback": [{"model": "fallback-model", "base_url": "https://gateway-b.example/v1"}],
        },
    )

    fb = _entry(llm_fallback_health(load_config(path)))

    assert fb["inherits_provider"] is True
    assert fb["inherits_key"] is False, "a cross-endpoint fallback must not inherit the key"
    assert fb["key_status"] == "cross_endpoint_no_key"


def test_explicit_entry_key_is_never_replaced_by_the_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _keys(monkeypatch)
    """An entry that names its own key keeps it, however it is expressed.

    ``load_config`` expands ``${ENV}`` references at load time, so through the
    production path the entry arrives as a literal and the resolver reports
    ``explicit``. The ``explicit_env`` status is only reachable by calling
    ``resolve_fallback_api_key`` with an unexpanded string, so asserting it here
    would pin a state the loader cannot produce. The invariant worth pinning is
    that the primary key is not substituted either way.
    """
    path = _write_config(
        tmp_path,
        {
            "provider": "openai",
            "model": "primary-model",
            "api_key": "${AUTOINFO_LLM_API_KEY}",
            "base_url": "https://gateway.example/v1",
            "fallback": [
                {
                    "model": "fallback-model",
                    "base_url": "https://gateway.example/v1",
                    "api_key": "${OTHER_VENDOR_KEY}",
                }
            ],
        },
    )

    cfg = load_config(path)
    fb = _entry(llm_fallback_health(cfg))

    assert cfg.llm.fallback[0].api_key == "other-vendor-secret", (
        "the loader must expand the entry's own reference, not the primary's"
    )
    assert fb["inherits_key"] is False
    assert fb["key_status"] == "explicit"


def test_no_primary_key_reports_that_rather_than_inheriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AUTOINFO_LLM_API_KEY", raising=False)
    """With no primary key configured there is nothing to inherit, and it must say so."""
    path = _write_config(
        tmp_path,
        {
            "provider": "openai",
            "model": "primary-model",
            "api_key": "",
            "base_url": "https://gateway.example/v1",
            "fallback": [{"model": "fallback-model", "base_url": "https://gateway.example/v1"}],
        },
    )

    fb = _entry(llm_fallback_health(load_config(path)))

    assert fb["inherits_key"] is False
    assert fb["key_status"] == "no_primary_key"


def test_fallback_entries_are_parsed_verbatim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _keys(monkeypatch)
    """Model and base_url come through the loader unchanged."""
    path = _write_config(
        tmp_path,
        {
            "provider": "openai",
            "model": "primary-model",
            "api_key": "${AUTOINFO_LLM_API_KEY}",
            "base_url": "https://gateway.example/v1",
            "fallback": [
                {"model": "first-fallback", "base_url": "https://b.example/v1"},
                {"model": "second-fallback", "base_url": "https://gateway.example/v1"},
            ],
        },
    )

    health = llm_fallback_health(load_config(path))

    assert health["count"] == 2
    assert [e["model"] for e in health["entries"]] == ["first-fallback", "second-fallback"]
    assert _entry(health, 0)["inherits_key"] is False
    assert _entry(health, 1)["inherits_key"] is True


def test_absent_fallback_reports_not_configured(tmp_path: Path) -> None:
    """An empty ``llm.fallback`` is reported honestly rather than inferred."""
    path = _write_config(
        tmp_path,
        {"provider": "openai", "model": "primary-model", "fallback": []},
    )

    health = llm_fallback_health(load_config(path))

    assert health["configured"] is False
    assert health["count"] == 0


@pytest.mark.skipif(
    os.environ.get("AUTOINFO_DEPLOYMENT_PIN") != "1",
    reason="deployment pin — opt in with AUTOINFO_DEPLOYMENT_PIN=1",
)
def test_real_deployment_config_parses_and_has_a_usable_fallback() -> None:
    """Opt-in check of the machine's actual config.

    Deliberately never asserts a specific model name: this reports what is
    configured so a human can eyeball it, instead of failing the build when
    they point AutoInfo at a different gateway.
    """
    if not DEPLOYMENT_CONFIG.is_file():
        pytest.skip(".autoinfo/config.yaml absent (gitignored)")

    cfg = load_config(DEPLOYMENT_CONFIG)
    health = llm_fallback_health(cfg)

    assert health["primary"]["provider"] == cfg.llm.provider
    for index, entry in enumerate(health["entries"]):
        assert entry["model"], f"fallback[{index}] has no model"
        if entry["inherits_key"]:
            assert entry["key_status"] == "inherited_same_gateway"
