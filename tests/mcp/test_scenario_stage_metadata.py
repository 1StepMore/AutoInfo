"""Scenario stage/level metadata is REQUIRED and enum-validated (T-A-01).

The stage×user coverage spine (A1-A7 pipeline × 18 user-lifecycle stages)
is only machine-measurable if every scenario declares which pipeline stage
it exercises and which user level it targets.  ``load_scenarios`` therefore
rejects a scenario that omits either key or carries an unknown value, and
``list_scenarios`` surfaces both for every loaded scenario.

Counts are dynamic: these tests assert over the live loader output, never a
hard-coded scenario total.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autoinfo.mcp.validation import (
    PIPELINE_STAGES,
    USER_LEVELS,
    list_scenarios,
    load_scenarios,
)

_STEPS = "steps:\n  - name: s\n    tool: health_check\n"


def _write(sd: Path, name: str, body: str) -> None:
    sd.mkdir(parents=True, exist_ok=True)
    (sd / f"{name}.yaml").write_text(body, encoding="utf-8")


def _valid_body(name: str, pipeline_stage: str, user_level: str) -> str:
    return (
        f"name: {name}\n"
        f"description: {name}\n"
        f"category: happy_path\n"
        f"pyramid_layer: component\n"
        f"pipeline_stage: {pipeline_stage}\n"
        f"user_level: {user_level}\n"
        f"{_STEPS}"
    )


class TestRequiredStageMetadata:
    def test_missing_pipeline_stage_fails_to_load(self, tmp_path: Path) -> None:
        sd = tmp_path / "scenarios"
        _write(
            sd,
            "no-stage",
            f"name: no-stage\ndescription: d\nuser_level: B2.4\n{_STEPS}",
        )
        with pytest.raises(ValueError, match="no-stage\\.yaml.*'pipeline_stage'"):
            load_scenarios(sd)

    def test_missing_user_level_fails_to_load(self, tmp_path: Path) -> None:
        sd = tmp_path / "scenarios"
        _write(
            sd,
            "no-level",
            "name: no-level\ndescription: d\n"
            "category: happy_path\npyramid_layer: component\n"
            f"pipeline_stage: A3\n{_STEPS}",
        )
        with pytest.raises(ValueError, match="no-level\\.yaml.*'user_level'"):
            load_scenarios(sd)

    def test_unknown_pipeline_stage_fails_to_load(self, tmp_path: Path) -> None:
        sd = tmp_path / "scenarios"
        _write(sd, "bad-stage", _valid_body("bad-stage", "A9", "B2.4"))
        with pytest.raises(ValueError, match="bad-stage\\.yaml.*'pipeline_stage'"):
            load_scenarios(sd)

    def test_unknown_user_level_fails_to_load(self, tmp_path: Path) -> None:
        sd = tmp_path / "scenarios"
        _write(sd, "bad-level", _valid_body("bad-level", "A3", "B9.9"))
        with pytest.raises(ValueError, match="bad-level\\.yaml.*'user_level'"):
            load_scenarios(sd)

    def test_valid_metadata_loads(self, tmp_path: Path) -> None:
        sd = tmp_path / "scenarios"
        _write(sd, "good", _valid_body("good", "A4", "B2.4"))
        scs = load_scenarios(sd)
        assert len(scs) == 1
        assert scs[0]["pipeline_stage"] == "A4"
        assert scs[0]["user_level"] == "B2.4"


class TestOnDiskLibraryTagged:
    def test_all_on_disk_scenarios_load_and_carry_valid_tags(self) -> None:
        scs = load_scenarios()
        assert scs, "load_scenarios() returned no scenarios"
        for sc in scs:
            assert sc["pipeline_stage"] in PIPELINE_STAGES, (
                f"scenario {sc['name']!r}: invalid pipeline_stage {sc.get('pipeline_stage')!r}"
            )
            assert sc["user_level"] in USER_LEVELS, (
                f"scenario {sc['name']!r}: invalid user_level {sc.get('user_level')!r}"
            )

    def test_list_scenarios_surfaces_both_fields(self) -> None:
        result = list_scenarios()
        assert result["count"] == len(result["scenarios"])
        assert result["count"] > 0
        for sc in result["scenarios"]:
            assert sc["pipeline_stage"] in PIPELINE_STAGES, (
                f"list_scenarios item {sc['name']!r} missing/invalid pipeline_stage"
            )
            assert sc["user_level"] in USER_LEVELS, (
                f"list_scenarios item {sc['name']!r} missing/invalid user_level"
            )
