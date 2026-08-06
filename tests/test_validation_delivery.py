"""Tests for scripts/validation_delivery.py delivery quality gates (E7, #131).

Covers:
- ``check_authenticity`` — per-artifact field-presence pre-check (md N/A-pass,
  JSON entry validation, example.com placeholder rejection)
- ``run_delivery_gates`` — D1-D3 (reusing autoinfo.quality unmodified) combined
  with authenticity into a unified gates dict + PASS/FAIL quality
- ``_package`` — gates/quality in manifest entries, 06-REJECTED/ output for
  failed artifacts, rejected summary in the manifest
"""
from __future__ import annotations

import importlib.util
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Load the real scripts/validation_delivery.py (same pattern as the sibling
# E3 test_validation_coverage.py) so the tests exercise the script's own code.
_SPEC = importlib.util.spec_from_file_location(
    "validation_delivery", ROOT / "scripts" / "validation_delivery.py"
)
assert _SPEC is not None and _SPEC.loader is not None
vd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(vd)

from autoinfo.quality import QualityResult  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _passing_result(name: str, details: dict[str, Any] | None = None) -> QualityResult:
    return QualityResult(gate_name=name, passed=True, score=1.0, details=details or {})


def _failing_result(name: str, error: str) -> QualityResult:
    return QualityResult(
        gate_name=name,
        passed=False,
        score=0.0,
        flagged=True,
        details={"action": "block", "error": error},
    )


def _all_pass_gates(product_output, context=None, delivery_gate_configs=None):
    """Fake quality.run_delivery_gates that always passes (isolation)."""
    return {
        "D1-ProductCompleteness": _passing_result("D1-ProductCompleteness"),
        "D2-FormatIntegrity": _passing_result("D2-FormatIntegrity"),
        "D3-Freshness": _passing_result("D3-Freshness"),
    }


def _zip_manifest(zip_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path) as zf:
        return json.loads(zf.read("manifest.json").decode("utf-8"))


def _zip_names(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path) as zf:
        return zf.namelist()


@pytest.fixture
def digest_md(tmp_path: Path) -> Path:
    """A realistic digest-style markdown with all three D1 sections."""
    p = tmp_path / "digest-2026-08-06.md"
    p.write_text(
        "# Weekly AI Digest\n\n"
        "## Executive Summary\n\nAI adoption accelerates.\n\n"
        "### Key Findings\n\n- LLM costs dropped 40%.\n\n"
        "### Recommendations\n\n- Adopt agent workflows.\n\n"
        "## Entries\n\n### 1. Some article\n\nBody text.\n",
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# check_authenticity
# ---------------------------------------------------------------------------


def test_check_authenticity_md_pass(tmp_path: Path):
    """A .md content file is text, not a structured entry -> N/A pass."""
    p = tmp_path / "digest.md"
    p.write_text("# Title\n\nplain content\n", encoding="utf-8")
    res = vd.check_authenticity(p)
    assert res["authenticity"] == "pass"
    assert "N/A" in res["reason"]


def test_check_authenticity_md_with_frontmatter_pass(tmp_path: Path):
    """md with source frontmatter still N/A-passes (field presence only)."""
    p = tmp_path / "entry.md"
    p.write_text(
        "---\nsource_url: https://pubmed.ncbi.nlm.nih.gov/123\n"
        "source_type: pubmed\nsource_platform: pubmed\n---\n\nBody.\n",
        encoding="utf-8",
    )
    res = vd.check_authenticity(p)
    assert res["authenticity"] == "pass"
    assert "frontmatter" in res["reason"]


def test_check_authenticity_html_pass(tmp_path: Path):
    """.html content files N/A-pass like markdown."""
    p = tmp_path / "digest.html"
    p.write_text("<html><body><h1>Digest</h1></body></html>", encoding="utf-8")
    assert vd.check_authenticity(p)["authenticity"] == "pass"


def test_check_authenticity_json_valid(tmp_path: Path):
    """JSON with fully-provenanced entries passes."""
    p = tmp_path / "agent.json"
    p.write_text(
        json.dumps({
            "entries": [{
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345",
                "source_type": "pubmed",
                "source_platform": "pubmed",
            }]
        }),
        encoding="utf-8",
    )
    res = vd.check_authenticity(p)
    assert res["authenticity"] == "pass"
    assert "complete source fields" in res["reason"]


def test_check_authenticity_json_example_com(tmp_path: Path):
    """JSON with an example.com placeholder URL fails."""
    p = tmp_path / "agent.json"
    p.write_text(
        json.dumps({
            "entries": [{
                "source_url": "https://example.com/article",
                "source_type": "web",
                "source_platform": "web",
            }]
        }),
        encoding="utf-8",
    )
    res = vd.check_authenticity(p)
    assert res["authenticity"] == "fail"
    assert "example.com" in res["reason"]


def test_check_authenticity_json_missing_fields(tmp_path: Path):
    """JSON entries missing source_type (or source_platform) fail."""
    p = tmp_path / "agent.json"
    p.write_text(
        json.dumps({
            "entries": [{
                "source_url": "https://arxiv.org/abs/2608.00001",
                "source_platform": "arxiv",
            }]
        }),
        encoding="utf-8",
    )
    res = vd.check_authenticity(p)
    assert res["authenticity"] == "fail"
    assert "source_type" in res["reason"]
    assert "source_platform" not in res["reason"] or "source_platform" in res["reason"]

    # A second entry missing source_platform also fails
    p.write_text(
        json.dumps({
            "entries": [{
                "source_url": "https://arxiv.org/abs/2608.00001",
                "source_type": "arxiv",
            }]
        }),
        encoding="utf-8",
    )
    res2 = vd.check_authenticity(p)
    assert res2["authenticity"] == "fail"
    assert "source_platform" in res2["reason"]


def test_check_authenticity_json_missing_source_url(tmp_path: Path):
    """JSON entry without source_url at all fails."""
    p = tmp_path / "agent.json"
    p.write_text(
        json.dumps({"entries": [{"title": "no url", "source_type": "x", "source_platform": "x"}]}),
        encoding="utf-8",
    )
    assert vd.check_authenticity(p)["authenticity"] == "fail"


def test_check_authenticity_json_no_entries_pass(tmp_path: Path):
    """JSON with no structured entries has nothing to verify -> pass."""
    p = tmp_path / "scenarios.json"
    p.write_text(json.dumps({"results": [{"name": "a", "status": "passed"}]}), encoding="utf-8")
    res = vd.check_authenticity(p)
    assert res["authenticity"] == "pass"


def test_check_authenticity_jsonl(tmp_path: Path):
    """JSONL entries are validated per line."""
    p = tmp_path / "items.jsonl"
    entry1 = json.dumps(
        {"source_url": "https://pubmed.ncbi.nlm.nih.gov/1",
         "source_type": "pubmed", "source_platform": "pubmed"}
    )
    entry2 = json.dumps(
        {"source_url": "https://example.com/fake", "source_type": "web", "source_platform": "web"}
    )
    p.write_text(entry1 + "\n" + entry2 + "\n", encoding="utf-8")
    res = vd.check_authenticity(p)
    assert res["authenticity"] == "fail"
    assert "example.com" in res["reason"]


def test_check_authenticity_binary_na_pass(tmp_path: Path):
    """Non-JSON binaries (mp3/pdf) are content, not structured entries."""
    p = tmp_path / "digest.mp3"
    p.write_bytes(b"\xff\xfb\x90\x00fake-mp3-bytes")
    assert vd.check_authenticity(p)["authenticity"] == "pass"


# ---------------------------------------------------------------------------
# run_delivery_gates
# ---------------------------------------------------------------------------


def test_run_delivery_gates_combined(tmp_path: Path, monkeypatch):
    """D1-D3 (from quality.py) combine with authenticity into one gates dict."""
    digest = tmp_path / "digest.md"
    digest.write_text(
        "# T\n\n## Executive Summary\n\ns\n\n### Key Findings\n\nk\n\n### Recommendations\n\nr\n",
        encoding="utf-8",
    )
    def _mixed(product_output, context=None, delivery_gate_configs=None):
        return {
            "D1-ProductCompleteness": _passing_result("D1-ProductCompleteness"),
            "D2-FormatIntegrity": _passing_result("D2-FormatIntegrity"),
            "D3-Freshness": _failing_result("D3-Freshness", "1 / 2 entries are stale"),
        }

    monkeypatch.setattr(vd, "_quality_run_delivery_gates", _mixed)
    res = vd.run_delivery_gates(digest, "PROCESSED")

    assert set(res["gates"]) == {"D1", "D2", "D3", "authenticity"}
    assert res["gates"]["D1"]["passed"] is True
    assert res["gates"]["D2"]["passed"] is True
    assert res["gates"]["D3"]["passed"] is False
    assert res["gates"]["authenticity"]["authenticity"] == "pass"
    assert res["quality"] == "FAIL"


def test_run_delivery_gates_all_pass_quality_pass(tmp_path: Path, monkeypatch):
    """PASS quality only when every gate passes."""
    digest = tmp_path / "digest.md"
    digest.write_text("# T\n\n## Executive Summary\n\ns\n", encoding="utf-8")
    monkeypatch.setattr(vd, "_quality_run_delivery_gates", _all_pass_gates)
    res = vd.run_delivery_gates(digest, "PROCESSED")
    assert res["quality"] == "PASS"
    assert res["gates"]["authenticity"]["authenticity"] == "pass"


def test_run_delivery_gates_authenticity_fail_flips_quality(tmp_path: Path, monkeypatch):
    """A failing authenticity pre-check fails quality even when D gates pass."""
    p = tmp_path / "agent.json"
    entry = {
        "entries": [{
            "source_url": "https://example.com/x",
            "source_type": "web",
            "source_platform": "web",
        }]
    }
    p.write_text(json.dumps(entry), encoding="utf-8")
    monkeypatch.setattr(vd, "_quality_run_delivery_gates", _all_pass_gates)
    res = vd.run_delivery_gates(p, "PROCESSED")
    assert res["quality"] == "FAIL"
    assert res["gates"]["authenticity"]["authenticity"] == "fail"


def test_run_delivery_gates_raw_bucket_skips_d_gates(tmp_path: Path, monkeypatch):
    """RAW-bucket files run with product_type=RAW so D gates trivially pass."""
    captured: dict[str, Any] = {}

    def _capture(product_output, context=None, delivery_gate_configs=None):
        captured["product_type"] = product_output.get("product_type")
        return {
            "D1-ProductCompleteness": _passing_result("D1-ProductCompleteness", {"skipped": True}),
            "D2-FormatIntegrity": _passing_result("D2-FormatIntegrity", {"skipped": True}),
            "D3-Freshness": _passing_result("D3-Freshness", {"skipped": True}),
        }

    monkeypatch.setattr(vd, "_quality_run_delivery_gates", _capture)
    raw = tmp_path / "cached.json"
    item = json.dumps(
        {"items": [{"source_url": "https://a.example.org/1",
                    "source_type": "rss", "source_platform": "rss"}]}
    )
    raw.write_text(item, encoding="utf-8")
    res = vd.run_delivery_gates(raw, "RAW")
    assert captured["product_type"] == "RAW"
    assert res["quality"] == "PASS"


def test_run_delivery_gates_real_quality_integration(tmp_path: Path):
    """The wrapper works against the real autoinfo.quality D1-D3 gates.

    A digest markdown with all three sections passes D1 (headings), D2
    (markdown trivially valid) and D3 (no dated entries to check).
    """
    digest = tmp_path / "digest.md"
    digest.write_text(
        "# Weekly Digest\n\n"
        "## Executive Summary\n\nSummary text.\n\n"
        "### Key Findings\n\n- Finding one.\n\n"
        "### Recommendations\n\n- Recommendation one.\n\n",
        encoding="utf-8",
    )
    res = vd.run_delivery_gates(digest, "PROCESSED")
    assert res["gates"]["D1"]["passed"] is True
    assert res["gates"]["D2"]["passed"] is True
    assert res["gates"]["D3"]["passed"] is True
    assert res["quality"] == "PASS"


def test_run_delivery_gates_json_freshness_real(tmp_path: Path):
    """JSON entries with recent collected_at pass the real D3 freshness gate."""
    fresh = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    p = tmp_path / "digest.json"
    p.write_text(
        json.dumps({
            "key_findings": ["k1"],
            "summary": "s",
            "recommendations": ["r1"],
            "entries": [{
                "title": "fresh entry",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/1",
                "source_type": "pubmed",
                "source_platform": "pubmed",
                "collected_at": fresh,
            }],
        }),
        encoding="utf-8",
    )
    res = vd.run_delivery_gates(p, "PROCESSED")
    assert res["gates"]["D1"]["passed"] is True
    assert res["gates"]["D3"]["passed"] is True
    assert res["gates"]["authenticity"]["authenticity"] == "pass"
    assert res["quality"] == "PASS"


def test_bucket_classification(tmp_path: Path):
    """_bucket maps delivery path patterns to RAW / KB / PROCESSED."""
    assert vd._bucket(Path("knowledge/medical-research/01-Raw/x/2026-08-06-a.md")) == "RAW"
    assert vd._bucket(Path("collections/medical-research/cached.json")) == "RAW"
    assert vd._bucket(Path("knowledge/medical-research/02-Draft/d.md")) == "KB"
    assert vd._bucket(Path("knowledge/medical-research/03-Wiki/w.md")) == "KB"
    assert vd._bucket(Path("outputs/digest.md")) == "PROCESSED"


# ---------------------------------------------------------------------------
# _package — manifest gates/quality + 06-REJECTED
# ---------------------------------------------------------------------------


def _package_with(tmp_path: Path, artifacts: list[Path], monkeypatch, quality_fake=None) -> Path:
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    if quality_fake is not None:
        monkeypatch.setattr(vd, "_quality_run_delivery_gates", quality_fake)
    return vd._package([{"path": str(p)} for p in artifacts], [], out)


def test_package_includes_gates_in_manifest(tmp_path: Path, monkeypatch):
    """Every manifest file entry carries a gates dict + PASS/FAIL quality."""
    digest = tmp_path / "digest.md"
    digest.write_text(
        "# T\n\n## Executive Summary\n\ns\n\n### Key Findings\n\nk\n\n### Recommendations\n\nr\n",
        encoding="utf-8",
    )
    zip_path = _package_with(tmp_path, [digest], monkeypatch, _all_pass_gates)

    manifest = _zip_manifest(zip_path)
    assert manifest["files"], "expected at least one delivered file"
    entry = manifest["files"][0]
    assert entry["file"].startswith("02-PROCESSED/") and entry["file"].endswith("/digest.md")
    assert entry["quality"] == "PASS"
    assert set(entry["gates"]) == {"D1", "D2", "D3", "authenticity"}
    assert entry["gates"]["D1"]["passed"] is True
    assert entry["gates"]["D2"]["passed"] is True
    assert entry["gates"]["D3"]["passed"] is True
    assert entry["gates"]["authenticity"]["authenticity"] == "pass"
    assert entry["gates"]["D1"]["gate"] == "D1-ProductCompleteness"


def test_package_rejects_failed(tmp_path: Path, monkeypatch):
    """FAIL-quality artifacts are moved to 06-REJECTED/ and listed as rejected."""
    digest = tmp_path / "digest.md"
    digest.write_text(
        "# T\n\n## Executive Summary\n\ns\n\n### Key Findings\n\nk\n\n### Recommendations\n\nr\n",
        encoding="utf-8",
    )
    bad = tmp_path / "bad.json"
    bad_entry = {
        "entries": [{
            "source_url": "https://example.com/x",
            "source_type": "web",
            "source_platform": "web",
        }]
    }
    bad.write_text(json.dumps(bad_entry), encoding="utf-8")
    zip_path = _package_with(tmp_path, [digest, bad], monkeypatch, _all_pass_gates)

    names = _zip_names(zip_path)
    assert any(n.startswith("02-PROCESSED/") and n.endswith("/digest.md") for n in names)
    assert any(n.startswith("06-REJECTED/") and n.endswith("/bad.json") for n in names)
    assert not any(n.startswith("02-PROCESSED/") and n.endswith("/bad.json") for n in names)

    manifest = _zip_manifest(zip_path)
    assert len(manifest["files"]) == 1
    assert len(manifest["rejected"]) == 1
    rejected = manifest["rejected"][0]
    assert rejected["file"].startswith("06-REJECTED/") and rejected["file"].endswith("/bad.json")
    assert "example.com" in rejected["reason"]
    assert rejected["reason"].startswith("authenticity:")


def test_package_rejects_d_gate_failure(tmp_path: Path, monkeypatch):
    """A D-gate failure (not just authenticity) also lands in 06-REJECTED."""
    digest = tmp_path / "digest.md"
    digest.write_text("# T\n\nplain, no sections\n", encoding="utf-8")

    def _d1_fails(product_output, context=None, delivery_gate_configs=None):
        return {
            "D1-ProductCompleteness": _failing_result(
                "D1-ProductCompleteness", "missing sections: key_findings, summary, recommendations"
            ),
            "D2-FormatIntegrity": _passing_result("D2-FormatIntegrity"),
            "D3-Freshness": _passing_result("D3-Freshness"),
        }

    zip_path = _package_with(tmp_path, [digest], monkeypatch, _d1_fails)
    manifest = _zip_manifest(zip_path)
    assert manifest["files"] == []
    assert len(manifest["rejected"]) == 1
    assert manifest["rejected"][0]["reason"].startswith("D1:")
    assert "missing sections" in manifest["rejected"][0]["reason"]


def test_package_kb_raw_artifacts_pass_gates(tmp_path: Path, monkeypatch):
    """KB/RAW-bucket artifacts pass the D gates (skipped) and stay delivered."""
    kb_entry = tmp_path / "knowledge" / "medical-research" / "03-Wiki" / "2026-08-06-x.md"
    kb_entry.parent.mkdir(parents=True)
    kb_entry.write_text(
        "---\ntitle: X\nsource_url: https://pubmed.ncbi.nlm.nih.gov/9\n"
        "source_type: pubmed\nsource_platform: pubmed\n---\n\nBody.\n",
        encoding="utf-8",
    )
    zip_path = _package_with(tmp_path, [kb_entry], monkeypatch, _all_pass_gates)
    manifest = _zip_manifest(zip_path)
    assert len(manifest["files"]) == 1
    entry = manifest["files"][0]
    assert entry["kind"] == "KB"
    assert entry["quality"] == "PASS"
    assert entry["gates"]["D1"]["passed"] is True
    assert manifest["rejected"] == []


def test_package_skips_missing_files(tmp_path: Path, monkeypatch):
    """Non-existent artifact paths are skipped without failing delivery."""
    ghost = tmp_path / "ghost.md"
    zip_path = _package_with(tmp_path, [ghost], monkeypatch, _all_pass_gates)
    manifest = _zip_manifest(zip_path)
    assert manifest["files"] == []
    assert manifest["rejected"] == []
