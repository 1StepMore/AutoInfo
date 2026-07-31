"""Tests for ``autoinfo init`` multi-domain behavior (issue #100).

Regression coverage: when ``init --demo A --demo B`` is run with multiple
domains, *all* domains must be embedded in ``config.yaml`` (the single
source of truth) and no misleading standalone ``sources.yaml`` may be
written (it previously only reflected the first domain).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from autoinfo.cli.init import _run_init


@pytest.fixture
def autoinfo_dir(tmp_path: Path) -> Path:
    return tmp_path / ".autoinfo"


def _read_config(path: Path) -> dict:
    assert path.is_file(), f"config.yaml not created at {path}"
    return yaml.safe_load(path.read_text())


class TestMultiDomainInit:
    """``_run_init`` with multiple domains (issue #100)."""

    def test_config_embeds_all_domains(
        self, autoinfo_dir: Path
    ) -> None:
        """config.yaml must contain sources/topics for EVERY requested domain."""
        _run_init(["medical-research", "ai-commercial"], autoinfo_dir)

        data = _read_config(autoinfo_dir / "config.yaml")
        domain_names = [d["name"] for d in data["domains"]]
        assert domain_names == ["medical-research", "ai-commercial"]

        # Both domains must carry their sources inline in config.yaml
        for d in data["domains"]:
            assert d["sources"], f"domain {d['name']!r} has no sources in config"

    def test_no_misleading_standalone_sources_yaml(
        self, autoinfo_dir: Path
    ) -> None:
        """No standalone sources.yaml — config.yaml is the single source of truth."""
        _run_init(["medical-research", "ai-commercial"], autoinfo_dir)

        assert not (autoinfo_dir / "sources.yaml").exists(), (
            "standalone sources.yaml must not be created: with multiple domains "
            "it only reflected the first domain (issue #100)"
        )

    def test_config_embeds_all_domains_sources(
        self, autoinfo_dir: Path
    ) -> None:
        """Sources for the 2nd domain must not be lost."""
        _run_init(["medical-research", "ai-commercial"], autoinfo_dir)

        data = _read_config(autoinfo_dir / "config.yaml")
        ai_commercial = next(
            d for d in data["domains"] if d["name"] == "ai-commercial"
        )
        source_names = [s["name"].lower() for s in ai_commercial["sources"]]
        assert any("techcrunch" in n for n in source_names), (
            f"ai-commercial sources missing from config: {source_names}"
        )


class TestSingleDomainInit:
    """Single-domain init must keep working (no regression)."""

    def test_config_created(self, autoinfo_dir: Path) -> None:
        _run_init(["medical-research"], autoinfo_dir)
        data = _read_config(autoinfo_dir / "config.yaml")
        assert [d["name"] for d in data["domains"]] == ["medical-research"]

    def test_no_standalone_sources_yaml_single_domain(
        self, autoinfo_dir: Path
    ) -> None:
        """sources.yaml removed even for single-domain init (consistency)."""
        _run_init(["medical-research"], autoinfo_dir)
        assert not (autoinfo_dir / "sources.yaml").exists()
