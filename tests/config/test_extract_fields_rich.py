"""Rich ``extract_fields`` entries are officially supported (#979).

Domain YAML may declare extraction fields either as plain strings or as rich
mappings (``{name, type, description, required}``).  ``DomainConfig`` keeps the
``list[str]`` invariant every consumer relies on (``llm.extract`` takes names)
and parks the rich metadata in ``extract_field_specs`` for display/docs only —
never for the LLM prompt.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from autoinfo.config import DomainConfig, config_to_dict, load_config, save_config

RICH_FIELDS: list[dict[str, Any]] = [
    {"name": "title", "type": "string", "description": "Video or article title", "required": True},
    {
        "name": "channel",
        "type": "string",
        "description": "Publisher, channel, or production company",
        "required": False,
    },
    {"name": "views", "type": "string", "description": "View count if available", "required": False},
]


def _config_dict(extract_fields: list[Any]) -> dict[str, Any]:
    return {
        "project": {"name": "T", "created_at": ""},
        "llm": {"provider": "openai", "model": "m", "api_key": ""},
        "domains": [
            {
                "name": "online-video",
                "active": True,
                "sources": [],
                "topics": [],
                "extract_fields": extract_fields,
            }
        ],
    }


def _write_config(tmp_path: Path, extract_fields: list[Any]) -> Path:
    config_dir = tmp_path / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "config.yaml"
    path.write_text(yaml.dump(_config_dict(extract_fields)), encoding="utf-8")
    return path


class TestRichExtractFieldsLoading:
    def test_names_are_all_plain_strings(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, RICH_FIELDS)
        domain = load_config(path).domains[0]
        assert domain.extract_fields == ["title", "channel", "views"]
        assert all(isinstance(name, str) for name in domain.extract_fields)

    def test_rich_specs_are_preserved(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, RICH_FIELDS)
        domain = load_config(path).domains[0]
        assert domain.extract_field_specs["title"] == {
            "type": "string",
            "description": "Video or article title",
            "required": True,
        }
        assert domain.extract_field_specs["channel"]["description"].startswith("Publisher")
        assert domain.extract_field_specs["channel"]["required"] is False

    def test_mixed_shapes_normalize(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, ["author", RICH_FIELDS[0]])
        domain = load_config(path).domains[0]
        assert domain.extract_fields == ["author", "title"]
        assert domain.extract_field_specs == {
            "title": {"type": "string", "description": "Video or article title", "required": True}
        }

    def test_unsupported_entries_are_skipped_with_a_warning(
        self, tmp_path: Path, caplog: Any
    ) -> None:
        path = _write_config(tmp_path, ["title", 42, {"type": "string"}])
        with caplog.at_level(logging.WARNING, logger="autoinfo.config"):
            domain = load_config(path).domains[0]
        assert domain.extract_fields == ["title"]
        assert domain.extract_field_specs == {}
        assert "extract_fields" in caplog.text

    def test_programmatic_construction_normalizes(self) -> None:
        domain = DomainConfig(name="d", extract_fields=RICH_FIELDS)  # type: ignore[arg-type]
        assert domain.extract_fields == ["title", "channel", "views"]
        assert domain.extract_field_specs["title"]["required"] is True


class TestRichExtractFieldsRoundTrip:
    def test_save_writes_rich_entries_back(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, RICH_FIELDS)
        config = load_config(path)
        raw = config_to_dict(config)
        assert raw["domains"][0]["extract_fields"] == RICH_FIELDS

    def test_load_save_load_preserves_names_and_specs(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, RICH_FIELDS)
        first = load_config(path).domains[0]
        save_config(load_config(path), path)
        second = load_config(path).domains[0]
        assert second.extract_fields == first.extract_fields
        assert second.extract_field_specs == first.extract_field_specs

    def test_specs_cannot_hijack_the_field_name(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, ["title"])
        config = load_config(path)
        config.domains[0].extract_field_specs["title"] = {"name": "hijacked", "type": "string"}
        raw = config_to_dict(config)
        assert raw["domains"][0]["extract_fields"] == [{"name": "title", "type": "string"}]


class TestLegacyStringExtractFields:
    def test_plain_strings_have_no_specs(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, ["title", "author"])
        domain = load_config(path).domains[0]
        assert domain.extract_fields == ["title", "author"]
        assert domain.extract_field_specs == {}

    def test_save_keeps_the_plain_string_shape(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, ["title", "author"])
        raw = config_to_dict(load_config(path))
        assert raw["domains"][0]["extract_fields"] == ["title", "author"]

    def test_legacy_config_round_trips_unchanged(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, ["title", "author"])
        save_config(load_config(path), path)
        domain = load_config(path).domains[0]
        assert domain.extract_fields == ["title", "author"]
        assert domain.extract_field_specs == {}
