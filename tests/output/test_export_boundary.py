"""Module-boundary characterization tests for the export family [T6].

These tests LOCK the CURRENT observable behavior of
:func:`autoinfo.output.export_kb` (plus its per-format ``_export_*`` dispatch)
BEFORE the export family is relocated into ``autoinfo.output.export`` (T7).
Per deep-modules-skill, the boundary under test is the PUBLIC ``export_kb``
call — never the private ``_export_*`` internals — exercised against a tmp KB
fixture with canned entries (no network, no LLM).

Golden byte-identity
--------------------
``tests/fixtures/golden/export_json.golden.json`` and
``tests/fixtures/golden/export_markdown.golden.md`` are committed renders of a
fixed 2-entry tmp KB.  After the T7 extraction the same ``export_kb`` calls
must reproduce them byte-for-byte.

Determinism guard (frozen / normalized fields)
----------------------------------------------
The current source embeds volatile values in some formats.  The render is made
deterministic before the goldens are compared:

* **Clock** — ``autoinfo.output.datetime`` is monkeypatched to
  :class:`_FrozenDateTime` so ``datetime.now(timezone.utc)`` returns
  ``FROZEN_NOW``.  This freezes: the ``<timestamp>`` in every export filename,
  the RSS ``<lastBuildDate>``, and the agent JSON-LD ``stats.generated_at``.
* **UUID** — ``autoinfo.output.uuid.uuid4`` is patched to return
  ``FROZEN_UUID``, freezing the agent JSON-LD top-level ``uuid``.
* **Absolute tmp paths** — the JSON export embeds each entry's absolute
  ``file_path``.  The golden comparison replaces the project root with the
  literal ``<PROJECT>`` (see :func:`_normalized_json`) so the byte-identity
  assertion never depends on the ``pytest`` tmp dir name.
* **tar metadata** — the markdown export is a ``.tar.gz`` whose member
  mtime/uid/gid/mode are inherently volatile; the golden compares the
  deterministic render (member name + file content, see
  :func:`_normalized_markdown`), not the raw archive bytes.
* **Entry ordering** — entries come from ``SQLiteIndex.list_entries`` which
  orders ``collected_at DESC``; the fixture uses distinct fixed timestamps so
  the order is pinned.

Optional-dependency formats
---------------------------
``pdf`` (weasyprint + markdown) and ``mobi`` (calibre ``ebook-convert``) are
tagged ``@pytest.mark.optional`` and skipped when their dependency is absent.
``epub`` is tagged optional too but now runs because ``ebooklib`` is present.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sqlite3
import tarfile
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest
import yaml

from autoinfo.kb import KBStore
from autoinfo.models import Item
from autoinfo.output import export_kb

# ---------------------------------------------------------------------------
# Determinism constants
# ---------------------------------------------------------------------------

FROZEN_NOW = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
FROZEN_TIMESTAMP = "20260828T120000Z"
FROZEN_UUID = uuid.UUID("00000000-0000-4000-8000-000000000000")

DOMAIN = "medical-research"
DOMAIN_LABEL = DOMAIN
# The exporter's exact-match source attribution keys on the configured source
# URL; configure one source per fixture entry URL so the attribution branch is
# exercised in the JSON golden.
_ENTRY_URLS = (
    "https://pubmed.ncbi.nlm.nih.gov/12345678/",
    "https://pubmed.ncbi.nlm.nih.gov/87654321/",
)

_GOLDEN_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "golden"
_MARKDOWN_GOLDEN = _GOLDEN_DIR / "export_markdown.golden.md"
_JSON_GOLDEN = _GOLDEN_DIR / "export_json.golden.json"

# Optional dependencies (absence => the format test skips, never fails).
HAVE_WEASYPRINT = importlib.util.find_spec("weasyprint") is not None
HAVE_EBOOKLIB = importlib.util.find_spec("ebooklib") is not None
HAVE_CALIBRE = shutil.which("ebook-convert") is not None


class _FrozenDateTime(datetime):
    """``datetime`` subclass whose ``now()`` returns :data:`FROZEN_NOW`."""

    @classmethod
    def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
        if tz is not None:
            return FROZEN_NOW.astimezone(tz)
        return FROZEN_NOW.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# tmp project fixture (canned 2-entry KB, no network / no LLM)
# ---------------------------------------------------------------------------

_SAMPLE_CONFIG: dict[str, Any] = {
    "project": {"name": "Export Boundary Test", "created_at": "2026-07-01"},
    "llm": {
        "provider": "openrouter",
        "model": "deepseek/deepseek-chat",
        "api_key": "test-key",
    },
    "domains": [
        {
            "name": DOMAIN,
            "active": True,
            "sources": [
                {
                    "name": "PubMed",
                    "type": "api",
                    "url": _ENTRY_URLS[0],
                    "quality_tier": 1,
                    "tos_classification": "open",
                },
                {
                    "name": "PubMed",
                    "type": "api",
                    "url": _ENTRY_URLS[1],
                    "quality_tier": 1,
                    "tos_classification": "open",
                },
            ],
            "topics": [{"name": "IVF breakthroughs", "keywords": ["IVF", "embryo"]}],
        },
    ],
}


def _build_project(root: Path) -> Path:
    """Create a tmp project with a config + exactly two canned KB entries.

    ``autoinfo.config.get_config_path`` is patched around ``store_entry`` so
    entry persistence is hermetic (vector search / multi-user never consult
    the developer's real ``.autoinfo/config.yaml``).
    """
    config_dir = root / ".autoinfo"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        yaml.dump(_SAMPLE_CONFIG, default_flow_style=False), encoding="utf-8"
    )

    with patch("autoinfo.config.get_config_path", return_value=config_path):
        store = KBStore(base_path=root / "knowledge")
        store.store_entry(
            Item(
                id="tg-1",
                source_name="PubMed",
                source_type="api",
                source_url=_ENTRY_URLS[0],
                title="Time-lapse embryo imaging improves IVF outcomes",
                content=(
                    "Time-lapse embryo imaging improved live birth rates in a "
                    "randomized controlled trial."
                ),
                collected_at="2026-07-15T10:00:00Z",
                domain=DOMAIN,
                source_platform="pubmed",
                topic_tags=["IVF"],
                language="en",
            )
        )
        store.store_entry(
            Item(
                id="tg-2",
                source_name="PubMed",
                source_type="api",
                source_url=_ENTRY_URLS[1],
                title="Embryo selection advances with AI scoring",
                content=(
                    "AI-based embryo scoring selects viable embryos more "
                    "accurately."
                ),
                collected_at="2026-07-16T10:00:00Z",
                domain=DOMAIN,
                source_platform="pubmed",
                topic_tags=["IVF"],
                language="en",
            )
        )
    return root


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A tmp project root (``.autoinfo/config.yaml`` + ``knowledge/`` + db)."""
    return _build_project(tmp_path)


@contextmanager
def _deterministic_env(project_dir: Path) -> Iterator[None]:
    """Patch the export family's volatile seams for a reproducible render.

    ``autoinfo.output.KBStore`` is also redirected to the tmp project so the
    GraphML exporter (which instantiates ``KBStore()`` directly) never touches
    the developer's real KB via ``_default_kb_base_path()``.
    """
    root = project_dir
    with (
        patch(
            "autoinfo.output.get_config_path",
            return_value=root / ".autoinfo" / "config.yaml",
        ),
        patch("autoinfo.output.datetime", _FrozenDateTime),
        patch("autoinfo.output.uuid.uuid4", return_value=FROZEN_UUID),
        patch(
            "autoinfo.output.KBStore",
            new=lambda *a, **k: KBStore(base_path=root / "knowledge"),
        ),
    ):
        yield


def _export(project_dir: Path, fmt: str, **kwargs: Any) -> dict[str, Any]:
    """Call the public boundary ``export_kb`` under the deterministic env."""
    with _deterministic_env(project_dir):
        return export_kb(domain=DOMAIN, format=fmt, **kwargs)


# ---------------------------------------------------------------------------
# Golden normalization helpers
# ---------------------------------------------------------------------------


def _normalized_json(export_path: Path, project_dir: Path) -> str:
    """Return the JSON export text with the tmp project root masked."""
    text = export_path.read_text(encoding="utf-8")
    return text.replace(str(project_dir.resolve()), "<PROJECT>")


def _normalized_markdown(tar_path: Path) -> str:
    """Return a deterministic render of the markdown tar.gz.

    Compares member names + extracted file contents (sorted), never the raw
    archive bytes whose tar metadata is volatile.
    """
    blocks: list[str] = []
    with tarfile.open(str(tar_path), "r:gz") as tar:
        for member in sorted(tar.getmembers(), key=lambda m: m.name):
            if not member.isfile():
                continue
            handle = tar.extractfile(member)
            assert handle is not None
            content = handle.read().decode("utf-8")
            blocks.append(f"===== {member.name} =====\n{content}")
    return "\n".join(blocks) + ("\n" if blocks else "")


def _render_markdown_golden(project_dir: Path) -> str:
    result = _export(project_dir, "markdown")
    return _normalized_markdown(Path(result["path"]))


def _render_json_golden(project_dir: Path) -> str:
    result = _export(project_dir, "json")
    return _normalized_json(Path(result["path"]), project_dir)


# ---------------------------------------------------------------------------
# Non-optional formats: markdown / json / sqlite / rss / sitemap / csv /
# graphml / agent / bundle
# ---------------------------------------------------------------------------


class TestExportMarkdown:
    def test_markdown_tarball_contains_kb_files(self, project: Path) -> None:
        result = _export(project, "markdown")

        assert result["format"] == "markdown"
        assert result["success"] is True
        assert result["domain"] == DOMAIN_LABEL
        assert result["entries_count"] == 2
        out_path = Path(result["path"])
        assert out_path.is_file()
        assert out_path.name == f"autoinfo-export-{DOMAIN}-{FROZEN_TIMESTAMP}.tar.gz"

        with tarfile.open(str(out_path), "r:gz") as tar:
            names = sorted(m.name for m in tar.getmembers() if m.isfile())
            contents = [
                tar.extractfile(m).read().decode("utf-8")  # type: ignore[union-attr]
                for m in sorted(tar.getmembers(), key=lambda m: m.name)
                if m.isfile()
            ]
        assert len(names) == 2
        assert all(n.startswith(f"{DOMAIN}/01-Raw/IVF/") for n in names)
        joined = "\n".join(contents)
        assert "Time-lapse embryo imaging improves IVF outcomes" in joined
        assert "Embryo selection advances with AI scoring" in joined


class TestExportJson:
    def test_json_array_with_attribution(self, project: Path) -> None:
        result = _export(project, "json")

        assert result["format"] == "json"
        assert result["entries_count"] == 2
        out_path = Path(result["path"])
        assert out_path.name == f"autoinfo-export-{DOMAIN}-{FROZEN_TIMESTAMP}.json"

        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert [e["title"] for e in data] == [
            "Embryo selection advances with AI scoring",
            "Time-lapse embryo imaging improves IVF outcomes",
        ]
        assert all(e["domain"] == DOMAIN for e in data)
        assert all(e["tags"] == ["IVF"] for e in data)
        # Source attribution enrichment (export_kb F46) keys on configured URL.
        assert data[0]["attribution"].startswith("Source: PubMed")
        assert data[1]["attribution"].startswith("Source: PubMed")


class TestExportSqlite:
    def test_filtered_sqlite_copy_has_both_entries(self, project: Path) -> None:
        result = _export(project, "sqlite")

        assert result["format"] == "sqlite"
        assert result["entries_count"] == 2
        out_path = Path(result["path"])
        assert out_path.name == f"autoinfo-export-{DOMAIN}-{FROZEN_TIMESTAMP}.db"

        conn = sqlite3.connect(str(out_path))
        try:
            rows = conn.execute(
                "SELECT title FROM entries ORDER BY collected_at DESC"
            ).fetchall()
            count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        finally:
            conn.close()
        assert count == 2
        assert [r[0] for r in rows] == [
            "Embryo selection advances with AI scoring",
            "Time-lapse embryo imaging improves IVF outcomes",
        ]


class TestExportRss:
    def test_rss_feed_structure(self, project: Path) -> None:
        result = _export(project, "rss")

        assert result["format"] == "rss"
        assert result["entries_count"] == 2
        out_path = Path(result["path"])
        assert out_path.name == f"autoinfo-rss-{DOMAIN}-{FROZEN_TIMESTAMP}.xml"

        root = ET.parse(str(out_path)).getroot()
        assert root.tag == "rss"
        channel = root.find("channel")
        assert channel is not None
        assert channel.findtext("title") == "AutoInfo - medical-research"
        # Frozen clock => deterministic lastBuildDate.
        assert channel.findtext("lastBuildDate") == format_datetime(FROZEN_NOW)
        items = channel.findall("item")
        assert len(items) == 2
        assert items[0].findtext("title") == "Embryo selection advances with AI scoring"
        assert items[0].findtext("link") == _ENTRY_URLS[1]


class TestExportSitemap:
    def test_sitemap_requires_base_url(self, project: Path) -> None:
        with pytest.raises(ValueError, match="base_url"):
            _export(project, "sitemap")

    def test_sitemap_contains_entry_urls(self, project: Path) -> None:
        result = _export(project, "sitemap", base_url="https://example.test")

        assert result["format"] == "sitemap"
        assert result["entries_count"] == 2
        out_path = Path(result["path"])
        assert out_path.name == "sitemap.xml"
        text = out_path.read_text(encoding="utf-8")
        ET.fromstring(text)  # must be valid XML
        for url in _ENTRY_URLS:
            assert url in text
        assert "https://example.test" in text


class TestExportCsv:
    def test_csv_rows_match_entries(self, project: Path) -> None:
        result = _export(project, "csv")

        assert result["format"] == "csv"
        assert result["entries_count"] == 2
        out_path = Path(result["path"])
        assert out_path.name == f"autoinfo-csv-{DOMAIN}-{FROZEN_TIMESTAMP}.csv"

        with out_path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 2
        assert {r["title"] for r in rows} == {
            "Time-lapse embryo imaging improves IVF outcomes",
            "Embryo selection advances with AI scoring",
        }
        # list-valued fields are serialized as JSON strings
        assert rows[0]["tags"] == '["IVF"]'


class TestExportGraphml:
    def test_graphml_scaffolding(self, project: Path) -> None:
        result = _export(project, "graphml")

        assert result["format"] == "graphml"
        assert result["success"] is True
        # No entities seeded in the fixture KB.
        assert result["entries_count"] == 0
        out_path = Path(result["path"])
        assert out_path.name == (
            f"autoinfo-graphml-{DOMAIN}-{FROZEN_TIMESTAMP}.graphml"
        )

        root = ET.parse(str(out_path)).getroot()
        ns = "{http://graphml.graphdrawing.org/xmlns}"
        assert root.tag == f"{ns}graphml"
        assert {k.get("id") for k in root.findall(f"{ns}key")} == {
            "k0", "k1", "k2", "k3"
        }
        assert root.find(f"{ns}graph") is not None


class TestExportAgent:
    def test_agent_jsonld_shape(self, project: Path) -> None:
        result = _export(project, "agent")

        assert result["@type"] == "KnowledgeBaseExport"
        assert result["@context"] == (
            "https://autoinfo.ai/schemas/knowledge-base-export-v1"
        )
        assert result["success"] is True
        assert result["domain"] == DOMAIN_LABEL
        # Frozen uuid + clock.
        assert result["uuid"] == str(FROZEN_UUID)
        assert result["stats"]["generated_at"] == FROZEN_NOW.isoformat()
        assert result["stats"]["total_entries"] == 2
        assert result["stats"]["exported_entries"] == 2
        assert len(result["entries"]) == 2
        assert result["entries"][0]["tags"] == ["IVF"]
        # export_kb appends the reserved collection_id key.
        assert result["collection_id"] is None


class TestExportBundle:
    def test_bundle_zip_core_formats(self, project: Path) -> None:
        result = _export(project, "bundle")

        assert result["format"] == "bundle"
        assert result["entries_count"] == 2
        out_path = Path(result["path"])
        assert out_path.name == f"bundle-{DOMAIN}-{FROZEN_TIMESTAMP}.zip"
        # json + md + yaml are always present; pdf is graceful-optional.
        assert {"json", "md", "yaml"}.issubset(set(result["formats"]))

        with zipfile.ZipFile(str(out_path), "r") as zf:
            names = set(zf.namelist())
            assert {"data.json", "summary.md", "metadata.yaml"}.issubset(names)
            data = json.loads(zf.read("data.json"))
            assert [e["title"] for e in data] == [
                "Embryo selection advances with AI scoring",
                "Time-lapse embryo imaging improves IVF outcomes",
            ]
            summary = zf.read("summary.md").decode("utf-8")
            assert summary.startswith("# medical-research — Knowledge Base Export")
            assert "**Entries:** 2" in summary
            metadata = yaml.safe_load(zf.read("metadata.yaml"))
            assert metadata["domain"] == DOMAIN_LABEL
            assert metadata["entry_count"] == 2
            assert metadata["export_version"] == "1.0"


class TestExportErrors:
    @pytest.mark.parametrize("fmt", ["docx", "xml", "", "MARKDOWN"])
    def test_unsupported_format_raises(self, project: Path, fmt: str) -> None:
        with pytest.raises(ValueError, match="Unsupported export format"):
            _export(project, fmt)

    def test_missing_config_raises_file_not_found(self, tmp_path: Path) -> None:
        with patch(
            "autoinfo.output.get_config_path",
            return_value=tmp_path / "nope" / ".autoinfo" / "config.yaml",
        ):
            with pytest.raises(FileNotFoundError, match="No configuration"):
                export_kb(domain=DOMAIN, format="json")


# ---------------------------------------------------------------------------
# Golden byte-identity (committed fixtures)
# ---------------------------------------------------------------------------


class TestGoldenRenders:
    def test_json_export_byte_identical_to_golden(self, project: Path) -> None:
        golden = _JSON_GOLDEN.read_text(encoding="utf-8")
        assert _render_json_golden(project) == golden

    def test_markdown_export_byte_identical_to_golden(self, project: Path) -> None:
        golden = _MARKDOWN_GOLDEN.read_text(encoding="utf-8")
        assert _render_markdown_golden(project) == golden

    def test_golden_files_exist_under_committed_fixtures(self) -> None:
        # Guard against goldens drifting back into gitignored locations.
        assert _MARKDOWN_GOLDEN.is_file()
        assert _JSON_GOLDEN.is_file()
        assert "tests/fixtures/golden" in str(_MARKDOWN_GOLDEN)
        assert "tests/fixtures/golden" in str(_JSON_GOLDEN)


# ---------------------------------------------------------------------------
# Optional-dependency formats: pdf / epub / mobi
# ---------------------------------------------------------------------------


class TestOptionalFormats:
    @pytest.mark.optional
    @pytest.mark.skipif(
        not HAVE_WEASYPRINT,
        reason=(
            "PDF export requires weasyprint + markdown "
            "(PyMuPDF/fitz is only used for PDF *import*)"
        ),
    )
    def test_pdf_export_writes_pdf(self, project: Path) -> None:
        result = _export(project, "pdf")

        assert result["format"] == "pdf"
        assert result["entries_count"] == 2
        out_path = Path(result["path"])
        assert out_path.is_file()
        assert out_path.read_bytes().startswith(b"%PDF")

    @pytest.mark.optional
    @pytest.mark.skipif(
        not HAVE_EBOOKLIB, reason="EPUB export requires ebooklib"
    )
    def test_epub_export_writes_epub(self, project: Path) -> None:
        result = _export(project, "epub")

        assert result["format"] == "epub"
        assert result["entries_count"] == 2
        assert result["data_b64"]
        out_path = Path(result["path"])
        assert out_path.is_file()
        assert out_path.read_bytes().startswith(b"PK")  # ZIP container

    @pytest.mark.optional
    @pytest.mark.skipif(
        not (HAVE_EBOOKLIB and HAVE_CALIBRE),
        reason="MOBI export requires ebooklib + calibre 'ebook-convert'",
    )
    def test_mobi_export_writes_mobi(self, project: Path) -> None:
        result = _export(project, "mobi")

        assert result["format"] == "mobi"
        assert result["entries_count"] == 2
        assert Path(result["path"]).is_file()


# ---------------------------------------------------------------------------
# Golden capture entry point (regenerate ONLY when current behavior changes)
# ---------------------------------------------------------------------------


def _capture_goldens() -> None:
    """Regenerate the committed goldens from the CURRENT source."""
    _GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        project_dir = _build_project(Path(td))
        _MARKDOWN_GOLDEN.write_text(
            _render_markdown_golden(project_dir), encoding="utf-8"
        )
        _JSON_GOLDEN.write_text(_render_json_golden(project_dir), encoding="utf-8")
    print(f"wrote {_MARKDOWN_GOLDEN}")
    print(f"wrote {_JSON_GOLDEN}")


if __name__ == "__main__":
    _capture_goldens()
