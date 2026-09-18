"""Tests for autoinfo.delivery.gate_report delivery-gate plumbing.

- ``_build_product_output`` — adapts an artifact file into the
  ``product_output`` dict quality.py expects (RAW/PROCESSED routing,
  per-format section extraction, metadata-JSON skip #169, agent @type
  passthrough #217)
- ``_serialize_gate_result`` — QualityResult -> JSON-serializable dict
- ``run_delivery_gates`` — real D1-D3 gates + authenticity, PASS/FAIL
- ``_failure_reason`` — human-readable failure summary

Real ``autoinfo.quality`` D gates run here: hermetic, no LLM, no network.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from autoinfo.delivery.gate_report import (
    _build_product_output,
    _failure_reason,
    _serialize_gate_result,
    run_delivery_gates,
)
from autoinfo.quality import QualityResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _complete_digest_md(tmp_path: Path, name: str = "digest-2026-09-04.md") -> Path:
    return _write(
        tmp_path,
        name,
        "# Weekly AI Digest\n\n"
        "## Executive Summary\n\nAI adoption accelerates.\n\n"
        "## Key Findings\n\n- LLM costs dropped 40%.\n\n"
        "## Recommendations\n\n- Adopt agent workflows.\n",
    )


def _incomplete_report_md(tmp_path: Path) -> Path:
    return _write(tmp_path, "broken-report.md", "# Broken Report\n\nNo canonical sections here.\n")


# ---------------------------------------------------------------------------
# _build_product_output
# ---------------------------------------------------------------------------


class TestBuildProductOutput:
    def test_raw_bucket_skips_inspection(self, tmp_path: Path) -> None:
        p = _complete_digest_md(tmp_path)
        assert _build_product_output(p, "RAW")["product_type"] == "RAW"

    def test_kb_bucket_skips_inspection(self, tmp_path: Path) -> None:
        p = _complete_digest_md(tmp_path)
        assert _build_product_output(p, "KB")["product_type"] == "RAW"

    def test_non_inspectable_format_runs_as_raw(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "product.pdf", "%PDF-1.4 fake")
        out = _build_product_output(p, "PROCESSED")
        assert out["product_type"] == "RAW"
        assert out["format"] == "markdown"

    def test_processed_md_digest_sections_and_type(self, tmp_path: Path) -> None:
        p = _complete_digest_md(tmp_path)
        out = _build_product_output(p, "PROCESSED")
        assert out["product_type"] == "digest"
        assert out["format"] == "markdown"
        assert out["key_findings"] == "- LLM costs dropped 40%."
        assert out["summary"] == "AI adoption accelerates."
        assert out["recommendations"] == "- Adopt agent workflows."
        assert "Weekly AI Digest" in out["body"]

    def test_processed_html_product(self, tmp_path: Path) -> None:
        p = _write(
            tmp_path,
            "report.html",
            "<h2>Key Findings</h2><p>Big result.</p><h2>Recommendations</h2><p>Act now.</p>",
        )
        out = _build_product_output(p, "PROCESSED")
        assert out["format"] == "html"
        assert out["product_type"] == "report"
        assert "Big result." in out["key_findings"]

    def test_unreadable_md_file_yields_empty_body(self, tmp_path: Path) -> None:
        d = tmp_path / "weird.md"
        d.mkdir()
        out = _build_product_output(d, "PROCESSED")
        assert out["body"] == ""
        assert out["key_findings"] == []

    def test_metadata_json_runs_as_raw(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "scenarios.json", json.dumps({"scenarios": []}))
        assert _build_product_output(p, "PROCESSED")["product_type"] == "RAW"

    def test_report_json_product_sections_and_entries(self, tmp_path: Path) -> None:
        payload = {
            "title": "Fresh digest",
            "summary": "s",
            "key_findings": ["k1"],
            "recommendations": ["r1"],
            "entries": [
                {
                    "title": "entry",
                    "source_url": "https://real.test/1",
                    "source_type": "api",
                    "source_platform": "pubmed",
                }
            ],
        }
        p = _write(tmp_path, "digest-fresh.json", json.dumps(payload))
        out = _build_product_output(p, "PROCESSED")
        assert out["product_type"] == "PROCESSED"
        assert out["format"] == "json"
        assert out["key_findings"] == ["k1"]
        assert out["summary"] == "s"
        assert len(out["entries"]) == 1

    def test_json_sections_fall_back_to_llm_synthesis(self, tmp_path: Path) -> None:
        payload = {
            "title": "t",
            "llm_synthesis": {
                "executive_summary": "nested summary",
                "next_steps": ["step"],
            },
        }
        p = _write(tmp_path, "report.json", json.dumps(payload))
        out = _build_product_output(p, "PROCESSED")
        assert out["summary"] == "nested summary"
        assert out["recommendations"] == ["step"]

    def test_agent_jsonld_carries_type_marker(self, tmp_path: Path) -> None:
        payload = {
            "@type": "KnowledgeDigest",
            "title": "t",
            "entries": [],
        }
        p = _write(tmp_path, "agent-digest.json", json.dumps(payload))
        out = _build_product_output(p, "PROCESSED")
        assert out["@type"] == "KnowledgeDigest"

    def test_unreadable_json_file_is_safe(self, tmp_path: Path) -> None:
        d = tmp_path / "weird.json"
        d.mkdir()
        out = _build_product_output(d, "PROCESSED")
        assert out["body"] == ""
        assert out["entries"] == []

    def test_empty_sections_default_shapes(self, tmp_path: Path) -> None:
        p = _write(tmp_path, "empty-report.md", "# Nothing here\n")
        out = _build_product_output(p, "PROCESSED")
        assert out["key_findings"] == []
        assert out["summary"] == ""
        assert out["recommendations"] == []
        assert out["entries"] == []


# ---------------------------------------------------------------------------
# _serialize_gate_result
# ---------------------------------------------------------------------------


class TestSerializeGateResult:
    def test_none_becomes_skipped_gate(self) -> None:
        out = _serialize_gate_result(None)
        assert out == {
            "gate": "unknown",
            "passed": True,
            "score": 0.0,
            "flagged": False,
            "details": {"skipped": True, "reason": "gate did not run"},
        }

    def test_quality_result_is_serialized(self) -> None:
        qr = QualityResult(
            gate_name="D1-ProductCompleteness",
            passed=False,
            score=0.0,
            flagged=True,
            details={"missing": ["summary"]},
        )
        out = _serialize_gate_result(qr)
        assert out["gate"] == "D1-ProductCompleteness"
        assert out["passed"] is False
        assert out["score"] == 0.0
        assert out["flagged"] is True
        assert out["details"] == {"missing": ["summary"]}

    def test_missing_attrs_fall_back_to_defaults(self) -> None:
        obj = SimpleNamespace(gate_name="X", passed=True, score=None, details=None)
        out = _serialize_gate_result(obj)
        assert out["score"] == 0.0
        assert out["flagged"] is False
        assert out["details"] == {}


# ---------------------------------------------------------------------------
# run_delivery_gates
# ---------------------------------------------------------------------------


class TestRunDeliveryGates:
    def test_complete_product_passes_all_gates(self, tmp_path: Path) -> None:
        p = _complete_digest_md(tmp_path)
        result = run_delivery_gates(p, "PROCESSED")
        assert result["quality"] == "PASS"
        assert set(result["gates"]) == {"D1", "D2", "D3", "authenticity"}
        for name in ("D1", "D2", "D3"):
            assert result["gates"][name]["passed"] is True, name
        assert result["gates"]["authenticity"]["authenticity"] == "pass"

    def test_incomplete_product_fails_d1(self, tmp_path: Path) -> None:
        p = _incomplete_report_md(tmp_path)
        result = run_delivery_gates(p, "PROCESSED")
        assert result["quality"] == "FAIL"
        assert result["gates"]["D1"]["passed"] is False
        assert "Missing sections" in json.dumps(result["gates"]["D1"]["details"])

    def test_raw_product_trivially_passes(self, tmp_path: Path) -> None:
        p = _incomplete_report_md(tmp_path)
        result = run_delivery_gates(p, "RAW")
        assert result["quality"] == "PASS"
        assert result["gates"]["D1"]["details"]["skipped"] is True

    def test_json_product_with_recent_timestamps_passes(self, tmp_path: Path) -> None:
        from datetime import datetime, timedelta, timezone

        payload = {
            "title": "Fresh digest",
            "summary": "s",
            "key_findings": ["k1"],
            "recommendations": ["r1"],
            "entries": [
                {
                    "title": "fresh entry",
                    "source_url": "https://real.test/1",
                    "source_type": "pubmed",
                    "source_platform": "pubmed",
                    "collected_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                }
            ],
        }
        p = _write(tmp_path, "digest-fresh.json", json.dumps(payload))
        result = run_delivery_gates(p, "PROCESSED")
        assert result["quality"] == "PASS"
        assert result["gates"]["D3"]["passed"] is True


# ---------------------------------------------------------------------------
# _failure_reason
# ---------------------------------------------------------------------------


_AUTH_OK = {"authenticity": "pass", "reason": "ok"}


class TestFailureReason:
    def test_d1_failure_uses_details_error(self) -> None:
        gates = {
            "D1": {"passed": False, "details": {"error": "Missing sections: summary"}},
            "D2": {"passed": True, "details": {}},
            "D3": {"passed": True, "details": {}},
            "authenticity": _AUTH_OK,
        }
        assert _failure_reason(gates) == "D1: Missing sections: summary"

    def test_d2_failure_uses_details_reason(self) -> None:
        gates = {
            "D2": {"passed": False, "details": {"reason": "bad format"}},
            "authenticity": _AUTH_OK,
        }
        assert _failure_reason(gates) == "D2: bad format"

    def test_gate_without_details_uses_generic_message(self) -> None:
        gates = {"D3": {"passed": False, "details": {}}, "authenticity": _AUTH_OK}
        assert _failure_reason(gates) == "D3: gate D3 failed"

    def test_authenticity_failure_is_reported(self) -> None:
        gates = {
            "authenticity": {
                "authenticity": "fail",
                "reason": "entry[0] missing source_url",
            }
        }
        assert _failure_reason(gates) == "authenticity: entry[0] missing source_url"

    def test_missing_authenticity_key_counts_as_failure(self) -> None:
        assert _failure_reason({}) == "authenticity: failed"

    def test_all_passing_gates_yield_generic_fallback(self) -> None:
        gates = {"D1": {"passed": True, "details": {}}, "authenticity": _AUTH_OK}
        assert _failure_reason(gates) == "quality gate failure"

    def test_multiple_reasons_are_joined(self) -> None:
        gates = {
            "D1": {"passed": False, "details": {"error": "empty"}},
            "D2": {"passed": False, "details": {"reason": "corrupt"}},
            "authenticity": {"authenticity": "fail", "reason": "no url"},
        }
        reason = _failure_reason(gates)
        assert reason == "D1: empty; D2: corrupt; authenticity: no url"
