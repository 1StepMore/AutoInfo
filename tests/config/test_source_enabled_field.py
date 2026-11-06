"""``SourceConfig.enabled`` as a first-class field (goal doc 2026-11-06 #2).

The two-state source model requires the enabled flag to live in the schema
— parseable from yaml (including the legacy settings-parasite form), bool-
coerced, visible to ``list_sources``, and preserved by config round-trips
(a disabled source must never silently resurrect through a save).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from autoinfo.config import SourceConfig, config_to_dict, load_config


def _write_config(tmp_path: Path, source_dict: dict) -> None:
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        "project": {"name": "T", "created_at": ""},
        "llm": {"provider": "openai", "model": "m", "api_key": ""},
        "domains": [
            {
                "name": "d1",
                "active": True,
                "sources": [source_dict],
                "topics": [],
            }
        ],
    }
    (config_dir / "config.yaml").write_text(yaml.dump(cfg), encoding="utf-8")


class TestEnabledFieldParsing:
    def test_default_is_enabled(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, {"name": "s1", "type": "rss", "url": "https://example.com"})
        cfg = load_config(Path.cwd() / ".autoinfo" / "config.yaml")
        assert cfg.domains[0].sources[0].enabled is True

    def test_yaml_false_parses_to_field(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            {"name": "s1", "type": "rss", "url": "https://example.com", "enabled": False},
        )
        source = load_config(Path.cwd() / ".autoinfo" / "config.yaml").domains[0].sources[0]
        assert source.enabled is False
        # Promoted out of the settings parasite — no legacy copy left behind.
        assert "enabled" not in source.settings

    def test_string_false_is_coerced(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            {"name": "s1", "type": "rss", "url": "https://example.com", "enabled": "false"},
        )
        assert (
            load_config(Path.cwd() / ".autoinfo" / "config.yaml").domains[0].sources[0].enabled
            is False
        )

    def test_programmatic_default(self) -> None:
        assert SourceConfig(name="s", type="rss", url="https://x").enabled is True


class TestEnabledFieldSerialization:
    def test_disabled_state_survives_round_trip(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _write_config(
            tmp_path,
            {"name": "s1", "type": "rss", "url": "https://example.com", "enabled": False},
        )
        cfg = load_config(Path.cwd() / ".autoinfo" / "config.yaml")
        raw = config_to_dict(cfg)
        assert raw["domains"][0]["sources"][0]["enabled"] is False

    def test_enabled_source_omits_the_key(self, tmp_path: Path, monkeypatch) -> None:
        """Default-enabled sources follow the write-only-non-defaults style."""
        monkeypatch.chdir(tmp_path)
        _write_config(tmp_path, {"name": "s1", "type": "rss", "url": "https://example.com"})
        cfg = load_config(Path.cwd() / ".autoinfo" / "config.yaml")
        raw = config_to_dict(cfg)
        assert "enabled" not in raw["domains"][0]["sources"][0]
