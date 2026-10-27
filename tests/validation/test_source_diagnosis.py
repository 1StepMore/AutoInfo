# mypy: ignore-errors
"""Tests for ``scripts/source_diagnosis.py`` (T5 of capability-27x3).

The classifier is pure filesystem, so the fixture trees below are built in
``tmp_path`` — the tests never write into the repository's ``collections/``.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "source_diagnosis.py"
SPEC = ROOT / "docs" / "dev" / "specs" / "end-user-matrix.yaml"
CONFIG_ROOT = ROOT / "src" / "autoinfo" / "data" / "domains"
COLLECTIONS = ROOT / "collections"

_SPEC_IMPORT = importlib.util.spec_from_file_location("source_diagnosis", SCRIPT)
assert _SPEC_IMPORT is not None and _SPEC_IMPORT.loader is not None
sd = importlib.util.module_from_spec(_SPEC_IMPORT)
_SPEC_IMPORT.loader.exec_module(sd)


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    return sd.diagnose(SPEC, CONFIG_ROOT, COLLECTIONS)


@pytest.fixture(scope="module")
def required() -> list[dict]:
    return sd.load_required_sources(SPEC)


def _write_run(source_dir: Path, status: str) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "_runs.json").write_text(
        json.dumps([{"timestamp": "2026-01-01T00:00:00+00:00", "status": status}]),
        encoding="utf-8",
    )


def _rows_by_pair(rows: list[dict]) -> dict[tuple[str, str], dict]:
    return {(r["domain"], r["source"]): r for r in rows}


# ---------------------------------------------------------------------------
# (a) row parity
# ---------------------------------------------------------------------------


def test_row_parity_is_exactly_the_78_required_pairs(rows, required):
    assert len(required) == 78
    assert [(r["domain"], r["source"]) for r in rows] == [
        (r["domain"], r["source"]) for r in required
    ]


# ---------------------------------------------------------------------------
# (b) bucket counts on the current tree
# ---------------------------------------------------------------------------


def test_bucket_counts_on_current_tree(rows):
    counts = sd.bucket_counts(rows)
    assert counts == {
        "satisfied": 9,
        "degraded": 5,
        "failing": 3,
        "never-attempted": 59,
        "configured-off": 2,
    }
    assert sum(counts.values()) == 78


# ---------------------------------------------------------------------------
# (c) configured-off pins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "domain,source",
    [("general-news", "wechat2rss"), ("online-education", "wanfang")],
)
def test_configured_off_sources(rows, domain, source):
    row = _rows_by_pair(rows)[(domain, source)]
    assert row["bucket"] == "configured-off"
    assert row["configured"] is True
    assert row["enabled"] is False
    assert row["recommendation"] in sd.RECOMMENDATIONS


# ---------------------------------------------------------------------------
# (d) failure-mode regression: last run status drives degraded
# ---------------------------------------------------------------------------


def test_error_run_moves_satisfied_source_to_degraded(tmp_path):
    collections = tmp_path / "collections"
    source_dir = collections / "ai-commercial" / "techcrunch" / "2026-01-01"
    source_dir.mkdir(parents=True)
    (source_dir / "item.json").write_text("{}", encoding="utf-8")
    _write_run(source_dir.parent, "success")

    before = _rows_by_pair(sd.diagnose(SPEC, CONFIG_ROOT, collections))
    assert before[("ai-commercial", "techcrunch")]["bucket"] == "satisfied"

    _write_run(source_dir.parent, "error")
    after = _rows_by_pair(sd.diagnose(SPEC, CONFIG_ROOT, collections))
    assert after[("ai-commercial", "techcrunch")]["bucket"] == "degraded"


# ---------------------------------------------------------------------------
# Detail guards: _runs.json is not an item; _failed/ is excluded
# ---------------------------------------------------------------------------


def test_runs_and_failed_are_not_counted_as_items(tmp_path):
    collections = tmp_path / "collections"
    source_dir = collections / "medical-research" / "pubmed" / "2026-01-01"
    source_dir.mkdir(parents=True)
    (source_dir / "item.json").write_text("{}", encoding="utf-8")
    _write_run(source_dir.parent, "success")
    failed = collections / "medical-research" / "_failed"
    failed.mkdir(parents=True)
    (failed / "rejected.json").write_text("{}", encoding="utf-8")

    row = _rows_by_pair(sd.diagnose(SPEC, CONFIG_ROOT, collections))[("medical-research", "pubmed")]
    assert row["collections_items"] == 1
    assert row["bucket"] == "satisfied"


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------


def test_render_markdown_carries_plan_columns(rows):
    text = sd.render_markdown(rows)
    header = text.splitlines()[text.splitlines().index("## Rows") + 2]
    for column in (
        "domain",
        "source",
        "configured",
        "enabled",
        "collections_items",
        "last_run_status",
        "last_run_at",
        "last_error",
        "bucket",
        "domain_stable_sources",
        "recommendation",
    ):
        assert column in header
    assert text.count("\n| ") >= len(rows)


DOC = ROOT / "docs" / "dev" / "source-diagnosis.md"


def _published_rows() -> list[list[str]]:
    section = DOC.read_text().split("## Full table", 1)[1]
    parsed: list[list[str]] = []
    for line in section.splitlines():
        if not line.startswith("| ") or line.startswith("| domain "):
            continue
        parsed.append([cell.strip() for cell in line.strip().strip("|").split(" | ")])
    return parsed


def test_published_doc_matches_classifier(rows):
    published = _published_rows()
    expected = [[r["domain"], r["source"], r["bucket"], r["recommendation"]] for r in rows]
    assert len(published) == 78
    assert [[c[0], c[1], c[8], c[10]] for c in published] == expected


def test_every_deferred_row_states_a_stable_domain(rows):
    deferred = [r for r in rows if r["recommendation"] == "deferred"]
    assert deferred, "expected at least one deferred row on the current tree"
    for row in deferred:
        assert int(row["domain_stable_sources"]) >= 2
