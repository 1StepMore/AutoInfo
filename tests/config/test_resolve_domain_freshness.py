"""Tests for ``resolve_domain_freshness`` — the single source of truth (#366).

Before #366 the domain→TTL mapping lived only in ``DomainConfig.__post_init__``
(the config-file path), while consumers fell back to a hardcoded ``90`` when no
config file was present — so the same domain was judged stale differently on
different machines.  These tests pin the resolver and the no-duplicate
invariant.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from autoinfo.config import (
    DEFAULT_FRESHNESS_THRESHOLD,
    DEFAULT_TTL_DAYS,
    DomainConfig,
    resolve_domain_freshness,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Issue #425: the previous guard grepped for the literal ``"ttl_days = 90"``,
# which never matched the real form ``ttl_days: int = 90`` — a vacuous test.
# These case-sensitive patterns match the forms the consumers actually carried,
# while leaving the canonical UPPERCASE constants untouched.
_TTL_LITERAL_PATTERNS = (
    re.compile(r"ttl_days[^=\n]{0,40}=\s*90\b"),  # ttl_days: int = 90 / ttl_days=90
    re.compile(r'"default"\s*:\s*90\b'),  # "default": 90
    re.compile(r"ttl_days[\"']\s*,\s*90\b"),  # arguments.get("ttl_days", 90)
)


def _write_config(root: Path, domains: list[dict[str, Any]]) -> None:
    config_dir = root / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        "project": {"name": "Test Project"},
        "llm": {"provider": "openrouter", "model": "deepseek/deepseek-chat"},
        "domains": domains,
    }
    (config_dir / "config.yaml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


@pytest.fixture
def hermetic_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated cwd + HOME so no real ``.autoinfo/config.yaml`` is found."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path


class TestResolveDomainFreshness:
    def test_medical_research_default_without_config(self, hermetic_project: Path) -> None:
        assert resolve_domain_freshness("medical-research") == (180, 0.5)

    def test_medical_research_same_with_config(self, hermetic_project: Path) -> None:
        _write_config(
            hermetic_project,
            [{"name": "medical-research", "active": True, "sources": []}],
        )
        assert resolve_domain_freshness("medical-research") == (180, 0.5)

    def test_explicit_configured_ttl_wins(self, hermetic_project: Path) -> None:
        _write_config(
            hermetic_project,
            [
                {
                    "name": "medical-research",
                    "active": True,
                    "sources": [],
                    "ttl_days": 42,
                    "freshness_threshold": 0.8,
                }
            ],
        )
        assert resolve_domain_freshness("medical-research") == (42, 0.8)

    def test_unknown_domain_uses_global_default(self, hermetic_project: Path) -> None:
        assert resolve_domain_freshness("totally-unknown") == (
            DEFAULT_TTL_DAYS,
            DEFAULT_FRESHNESS_THRESHOLD,
        )

    def test_domain_config_post_init_still_maps(self) -> None:
        assert DomainConfig(name="medical-research").ttl_days == 180
        assert DomainConfig(name="medical-research", ttl_days=42).ttl_days == 42


class TestNoDuplicateFallback:
    def test_consumers_have_no_hardcoded_ttl_literal(self) -> None:
        violations: list[str] = []
        for py in sorted((_REPO_ROOT / "src" / "autoinfo").rglob("*.py")):
            if py.name == "config.py":
                continue
            for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), start=1):
                if any(p.search(line) for p in _TTL_LITERAL_PATTERNS):
                    violations.append(f"{py.relative_to(_REPO_ROOT)}:{lineno}: {line.strip()}")
        assert violations == [], (
            "Hardcoded TTL literal(s) outside config.py — import DEFAULT_TTL_DAYS "
            "instead:\n" + "\n".join(violations)
        )
