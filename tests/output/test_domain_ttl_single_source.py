"""Output-layer regression for #366: domain TTL is config-independent.

The teaching-layer stale filter (``_filter_stale_entries``) used to fall back
to a hardcoded ``ttl_days = 90`` when no config file was present, so a
``medical-research`` entry (domain TTL 180) was judged stale differently on a
machine with a project config than on one without.  These tests assert the
same domain resolves the same TTL with and without a config file.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from autoinfo.config import resolve_domain_freshness
from autoinfo.output import _filter_stale_entries

_AGE_60_DAYS = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()


def _entry(domain: str) -> dict[str, Any]:
    return {
        "entry_id": "e-366",
        "title": "A medical result",
        "summary": "Summary.",
        "source_url": "https://example.com/a",
        "source_type": "rss",
        "source_platform": "pubmed",
        "domain": domain,
        "collected_at": _AGE_60_DAYS,
    }


def _write_config(root: Path, domain: dict[str, Any]) -> None:
    config_dir = root / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        "project": {"name": "Test Project"},
        "llm": {"provider": "openrouter", "model": "deepseek/deepseek-chat"},
        "domains": [domain],
    }
    (config_dir / "config.yaml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


@pytest.fixture
def hermetic_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path


class TestStaleFilterUsesSingleSource:
    def test_medical_research_entry_fresh_without_config(self, hermetic_project: Path) -> None:
        entry = _entry("medical-research")
        kept = _filter_stale_entries([entry], "medical-research")
        assert len(kept) == 1
        assert kept[0]["is_stale"] is False

    def test_same_domain_fresh_with_config(self, hermetic_project: Path) -> None:
        _write_config(hermetic_project, {"name": "medical-research", "active": True})
        entry = _entry("medical-research")
        kept = _filter_stale_entries([entry], "medical-research")
        assert len(kept) == 1

    def test_unknown_domain_stale_at_60_days(self, hermetic_project: Path) -> None:
        entry = _entry("general-news")
        kept = _filter_stale_entries([entry], "general-news")
        assert kept == []

    def test_explicit_config_ttl_overrides_domain_default(self, hermetic_project: Path) -> None:
        _write_config(
            hermetic_project,
            {"name": "medical-research", "active": True, "ttl_days": 30},
        )
        entry = _entry("medical-research")
        kept = _filter_stale_entries([entry], "medical-research")
        assert kept == []

    def test_resolver_and_filter_agree_without_config(self, hermetic_project: Path) -> None:
        assert resolve_domain_freshness("medical-research")[0] == 180
        entry = _entry("medical-research")
        assert len(_filter_stale_entries([entry], "medical-research")) == 1
