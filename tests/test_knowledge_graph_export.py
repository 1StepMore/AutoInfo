"""Tests for knowledge graph export — CLI command + KBStore.export_knowledge_graph.

Covers:
    - KBStore.export_knowledge_graph returns structured data
    - Domain filter isolates entities
    - JSON export produces valid JSON with correct structure
    - GraphML export produces valid XML
    - CSV export produces two files with headers
    - CLI help shows expected options
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pytest

from autoinfo.kb import KBStore


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def store_with_data(tmp_path: Path) -> KBStore:
    """A KBStore with entities in two domains for export testing."""
    store = KBStore(base_path=tmp_path / "knowledge")

    # Medical domain entities
    store.store_entities(
        "entry-med-1", "medical-research",
        [
            {"name": "CRISPR", "type": "technology"},
            {"name": "Gene Therapy", "type": "concept"},
            {"name": "AAV Vector", "type": "technology"},
        ],
    )
    # AI domain entities (should not leak into medical exports)
    store.store_entities(
        "entry-ai-1", "ai-commercial",
        [
            {"name": "Transformer", "type": "architecture"},
            {"name": "GPT-4", "type": "model"},
        ],
    )
    return store


# ===================================================================
# KBStore.export_knowledge_graph
# ===================================================================


class TestExportKnowledgeGraph:
    """Unit tests for KBStore.export_knowledge_graph."""

    def test_export_returns_expected_structure(self, store_with_data: KBStore) -> None:
        """Export returns dict with domain, exported_at, entities, relations."""
        result = store_with_data.export_knowledge_graph(domain="medical-research")
        assert "domain" in result
        assert "exported_at" in result
        assert "entities" in result
        assert "relations" in result
        assert result["domain"] == "medical-research"

    def test_export_contains_all_entities(self, store_with_data: KBStore) -> None:
        """All entities for the domain are included."""
        result = store_with_data.export_knowledge_graph(domain="medical-research")
        names = {e["name"] for e in result["entities"]}
        assert "CRISPR" in names
        assert "Gene Therapy" in names
        assert "AAV Vector" in names

    def test_export_domain_filter_excludes_other_domains(
        self, store_with_data: KBStore
    ) -> None:
        """Entities from other domains are excluded."""
        result = store_with_data.export_knowledge_graph(domain="medical-research")
        names = {e["name"] for e in result["entities"]}
        assert "Transformer" not in names
        assert "GPT-4" not in names

    def test_export_empty_domain_returns_all(
        self, store_with_data: KBStore
    ) -> None:
        """Empty domain string exports all domains."""
        result = store_with_data.export_knowledge_graph(domain="")
        assert result["domain"] == "*"
        names = {e["name"] for e in result["entities"]}
        assert "CRISPR" in names
        assert "Transformer" in names
        assert len(result["entities"]) >= 5

    def test_export_relations_included(self, store_with_data: KBStore) -> None:
        """Relations between entities are included in export."""
        result = store_with_data.export_knowledge_graph(domain="medical-research")
        assert isinstance(result["relations"], list)

    def test_export_has_timestamp(self, store_with_data: KBStore) -> None:
        """exported_at is an ISO-formatted timestamp."""
        result = store_with_data.export_knowledge_graph(domain="medical-research")
        from datetime import datetime

        # Should parse as ISO datetime
        parsed = datetime.fromisoformat(result["exported_at"])
        assert parsed is not None


# ===================================================================
# CLI — knowledge graph export
# ===================================================================


@pytest.fixture
def cli_runner() -> Any:
    from typer.testing import CliRunner
    return CliRunner()


@pytest.fixture
def app() -> Any:
    from autoinfo.cli import app
    return app


class TestCliKnowledgeGraphExport:
    """Tests for the ``autoinfo knowledge graph export`` CLI command."""

    def test_export_shows_in_help(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo --help`` lists the knowledge subcommand."""
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "knowledge" in result.stdout

    def test_graph_shows_in_knowledge_help(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo knowledge --help`` lists the graph subcommand."""
        result = cli_runner.invoke(app, ["knowledge", "--help"])
        assert result.exit_code == 0
        assert "graph" in result.stdout

    def test_export_shows_in_graph_help(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo knowledge graph --help`` lists the export command."""
        result = cli_runner.invoke(app, ["knowledge", "graph", "--help"])
        assert result.exit_code == 0
        assert "export" in result.stdout

    def test_export_help_shows_options(self, cli_runner: Any, app: Any) -> None:
        """``autoinfo knowledge graph export --help`` shows --domain, --format, --output."""
        result = cli_runner.invoke(app, ["knowledge", "graph", "export", "--help"])
        assert result.exit_code == 0
        assert "--domain" in result.stdout
        assert "--format" in result.stdout
        assert "--output" in result.stdout

    def test_export_json_creates_file(
        self, cli_runner: Any, app: Any, tmp_path: Path
    ) -> None:
        """Export as JSON writes a valid JSON file with correct structure."""
        # Create a KBStore with data in tmp_path and chdir there
        original_cwd = Path.cwd()
        os.chdir(str(tmp_path))
        try:
            store = KBStore(base_path=tmp_path / "knowledge")
            store.store_entities(
                "entry-1", "test-domain",
                [{"name": "EntityA", "type": "concept"}, {"name": "EntityB", "type": "concept"}],
            )

            out_file = tmp_path / "kg_export_test.json"
            result = cli_runner.invoke(
                app,
                [
                    "knowledge", "graph", "export",
                    "--domain", "test-domain",
                    "--format", "json",
                    "--output", str(out_file),
                ],
            )
            assert result.exit_code == 0, f"CLI failed: {result.stdout} {result.stderr}"
            assert out_file.exists()

            data = json.loads(out_file.read_text(encoding="utf-8"))
            assert data["domain"] == "test-domain"
            assert "entities" in data
            assert "relations" in data
            assert "exported_at" in data
            names = {e["name"] for e in data["entities"]}
            assert "EntityA" in names
            assert "EntityB" in names
        finally:
            os.chdir(str(original_cwd))

    def test_export_domain_filter_excludes_other(
        self, cli_runner: Any, app: Any, tmp_path: Path
    ) -> None:
        """Export with domain filter excludes entities from other domains."""
        original_cwd = Path.cwd()
        os.chdir(str(tmp_path))
        try:
            store = KBStore(base_path=tmp_path / "knowledge")
            store.store_entities(
                "e1", "domain-a",
                [{"name": "DomainA-Entity", "type": "concept"}],
            )
            store.store_entities(
                "e2", "domain-b",
                [{"name": "DomainB-Entity", "type": "concept"}],
            )

            out_file = tmp_path / "kg_filter_test.json"
            result = cli_runner.invoke(
                app,
                [
                    "knowledge", "graph", "export",
                    "--domain", "domain-a",
                    "--format", "json",
                    "--output", str(out_file),
                ],
            )
            assert result.exit_code == 0, f"CLI failed: {result.stdout}"
            assert out_file.exists()

            data = json.loads(out_file.read_text(encoding="utf-8"))
            names = {e["name"] for e in data["entities"]}
            assert "DomainA-Entity" in names
            assert "DomainB-Entity" not in names
        finally:
            os.chdir(str(original_cwd))

    def test_export_graphml_creates_valid_xml(
        self, cli_runner: Any, app: Any, tmp_path: Path
    ) -> None:
        """Export as GraphML produces valid XML."""
        original_cwd = Path.cwd()
        os.chdir(str(tmp_path))
        try:
            store = KBStore(base_path=tmp_path / "knowledge")
            store.store_entities(
                "e1", "test-domain",
                [{"name": "NodeA", "type": "concept"}, {"name": "NodeB", "type": "concept"}],
            )

            out_file = tmp_path / "kg_export.graphml"
            result = cli_runner.invoke(
                app,
                [
                    "knowledge", "graph", "export",
                    "--domain", "test-domain",
                    "--format", "graphml",
                    "--output", str(out_file),
                ],
            )
            assert result.exit_code == 0
            assert out_file.exists()

            # Parse as XML — should not raise
            tree = ET.parse(str(out_file))
            root = tree.getroot()
            # Should have a graph element
            assert root.find(".//{http://graphml.graphdrawing.org/xmlns}graph") is not None
        finally:
            os.chdir(str(original_cwd))

    def test_export_csv_creates_two_files(
        self, cli_runner: Any, app: Any, tmp_path: Path
    ) -> None:
        """Export as CSV produces entities.csv and relations.csv."""
        original_cwd = Path.cwd()
        os.chdir(str(tmp_path))
        try:
            store = KBStore(base_path=tmp_path / "knowledge")
            store.store_entities(
                "e1", "test-domain",
                [{"name": "NodeA", "type": "concept"}, {"name": "NodeB", "type": "concept"}],
            )

            out_stem = tmp_path / "kg_csv_export"
            result = cli_runner.invoke(
                app,
                [
                    "knowledge", "graph", "export",
                    "--domain", "test-domain",
                    "--format", "csv",
                    "--output", str(out_stem),
                ],
            )
            assert result.exit_code == 0

            entities_csv = Path(f"{out_stem}_entities.csv")
            relations_csv = Path(f"{out_stem}_relations.csv")
            assert entities_csv.exists()
            assert relations_csv.exists()

            # Check headers
            content = entities_csv.read_text(encoding="utf-8")
            assert "entity_id,name,type,domain" in content
        finally:
            os.chdir(str(original_cwd))

    def test_export_invalid_format_shows_error(
        self, cli_runner: Any, app: Any
    ) -> None:
        """Unsupported format produces an error message."""
        result = cli_runner.invoke(
            app,
            [
                "knowledge", "graph", "export",
                "--domain", "test",
                "--format", "pdf",
            ],
        )
        assert result.exit_code == 1
        assert "Unsupported format" in result.stdout
