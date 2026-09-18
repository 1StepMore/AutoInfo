"""Tests for autoinfo.delivery.gate_report per-product gate reports.

- ``_qa_product_key`` — deterministic, filesystem-safe, collision-free keys
- ``_qa_gate_row`` — the honest gates array (D1-D3 + authenticity)
- ``_build_qa_gate_report`` — md+json pairing with the process-layer
  honesty note; records only what was actually determined
- ``write_gate_report`` — single-product entry point: writes
  ``gate-report-<key>.{md,json}`` and returns the delivery determination
"""

from __future__ import annotations

import json
from pathlib import Path

from autoinfo.delivery.gate_report import (
    _build_qa_gate_report,
    _qa_gate_row,
    _qa_product_key,
    write_gate_report,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _passing_gates() -> dict:
    return {
        "D1": {"passed": True, "details": {"missing": []}},
        "D2": {"passed": True, "details": {}},
        "D3": {"passed": True, "details": {}},
        "authenticity": {
            "authenticity": "pass",
            "reason": "1 structured entry with complete source fields",
        },
    }


def _failing_gates() -> dict:
    return {
        "D1": {"passed": False, "details": {"error": "Missing sections: summary"}},
        "D2": {"passed": True, "details": {}},
        "D3": {"passed": True, "details": {}},
        "authenticity": {
            "authenticity": "fail",
            "reason": "entry[0] missing source_url",
        },
    }


def _passing_digest(tmp_path: Path, name: str = "digest-2026-09-04.md") -> Path:
    p = tmp_path / name
    p.write_text(
        "# Weekly AI Digest\n\n"
        "## Executive Summary\n\nAI adoption accelerates.\n\n"
        "## Key Findings\n\n- LLM costs dropped 40%.\n\n"
        "## Recommendations\n\n- Adopt agent workflows.\n",
        encoding="utf-8",
    )
    return p


def _broken_report(tmp_path: Path) -> Path:
    p = tmp_path / "broken-report.md"
    p.write_text("# Broken Report\n\nNo canonical sections here.\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# _qa_product_key
# ---------------------------------------------------------------------------


class TestQaProductKey:
    def test_stem_becomes_key(self) -> None:
        used: set[str] = set()
        assert _qa_product_key(Path("digest.md"), used) == "digest"

    def test_same_stem_twice_gets_suffixes(self) -> None:
        used: set[str] = set()
        k1 = _qa_product_key(Path("digest.md"), used)
        k2 = _qa_product_key(Path("digest.json"), used)
        k3 = _qa_product_key(Path("digest.md"), used)
        assert (k1, k2, k3) == ("digest", "digest-2", "digest-3")

    def test_nested_path_joins_directory_segments(self) -> None:
        used: set[str] = set()
        key = _qa_product_key(Path("outputs/med/sub/dir/digest.json"), used)
        assert key == "outputs__med__sub__dir__digest"

    def test_unsafe_characters_are_replaced(self) -> None:
        used: set[str] = set()
        key = _qa_product_key(Path("odd name/space file.md"), used)
        assert "/" not in key and " " not in key
        assert key == "odd_name__space_file"

    def test_keys_are_registered_in_used_set(self) -> None:
        used: set[str] = set()
        _qa_product_key(Path("a.md"), used)
        assert "a" in used


# ---------------------------------------------------------------------------
# _qa_gate_row
# ---------------------------------------------------------------------------


class TestQaGateRow:
    def test_passing_gates_array(self) -> None:
        rows = _qa_gate_row(_passing_gates())
        assert [r["gate"] for r in rows] == ["D1", "D2", "D3", "authenticity"]
        assert all(r["passed"] for r in rows)

    def test_failing_gates_reported_honestly(self) -> None:
        rows = _qa_gate_row(_failing_gates())
        by_gate = {r["gate"]: r for r in rows}
        assert by_gate["D1"]["passed"] is False
        assert by_gate["D1"]["details"] == {"error": "Missing sections: summary"}
        assert by_gate["authenticity"]["passed"] is False
        assert by_gate["authenticity"]["details"] == "entry[0] missing source_url"

    def test_missing_gate_defaults_to_passed(self) -> None:
        rows = _qa_gate_row({})
        assert [r["gate"] for r in rows] == ["D1", "D2", "D3", "authenticity"]
        for row in rows[:3]:
            assert row["passed"] is True
            assert row["details"] == {}
        assert rows[3]["passed"] is False
        assert rows[3]["details"] == ""


# ---------------------------------------------------------------------------
# _build_qa_gate_report
# ---------------------------------------------------------------------------


class TestBuildQaGateReport:
    def test_delivered_report_md_and_json_pairing(self) -> None:
        md_text, json_text = _build_qa_gate_report(
            "digest",
            product="digest-2026-09-04.md",
            kind="PROCESSED",
            delivered=True,
            quality="PASS",
            gates=_passing_gates(),
        )
        assert md_text.startswith("# Gate Report — digest-2026-09-04.md")
        assert "- Delivered: yes" in md_text
        assert "- Quality: PASS" in md_text
        assert "Rejection reason" not in md_text
        assert "## Gates" in md_text
        assert "## Scope Note" in md_text
        for gate in ("D1", "D2", "D3", "authenticity"):
            assert gate in md_text

        payload = json.loads(json_text)
        assert payload["product"] == "digest-2026-09-04.md"
        assert payload["product_key"] == "digest"
        assert payload["kind"] == "PROCESSED"
        assert payload["delivered"] is True
        assert payload["rejected_reason"] == ""
        assert payload["quality"] == "PASS"
        assert [g["gate"] for g in payload["gates"]] == [
            "D1",
            "D2",
            "D3",
            "authenticity",
        ]

    def test_honesty_note_in_both_formats(self) -> None:
        md_text, json_text = _build_qa_gate_report(
            "k",
            product="p.md",
            kind="PROCESSED",
            delivered=True,
            quality="PASS",
            gates=_passing_gates(),
        )
        payload = json.loads(json_text)
        assert "G0-G5" in payload["layer_note"]
        assert "process" in payload["layer_note"]
        assert "G0-G5" in md_text and "process" in md_text

    def test_rejected_report_carries_reason(self) -> None:
        md_text, json_text = _build_qa_gate_report(
            "broken-report",
            product="broken-report.md",
            kind="PROCESSED",
            delivered=False,
            quality="FAIL",
            gates=_failing_gates(),
            rejected_reason="D1: Missing sections: summary",
        )
        assert "- Delivered: no (rejected)" in md_text
        assert "- Rejection reason: D1: Missing sections: summary" in md_text
        payload = json.loads(json_text)
        assert payload["delivered"] is False
        assert payload["quality"] == "FAIL"
        assert payload["rejected_reason"] == "D1: Missing sections: summary"

    def test_md_gate_table_renders_pass_fail_columns(self) -> None:
        md_text, _ = _build_qa_gate_report(
            "k",
            product="p.md",
            kind="PROCESSED",
            delivered=False,
            quality="FAIL",
            gates=_failing_gates(),
        )
        assert "| D1 | FAIL |" in md_text
        assert "| D2 | PASS |" in md_text
        assert "| authenticity | FAIL |" in md_text

    def test_dict_details_render_error_then_reason_then_json(self) -> None:
        gates = {
            "D1": {"passed": False, "details": {"error": "err-text"}},
            "D2": {"passed": False, "details": {"reason": "why-text"}},
            "D3": {"passed": True, "details": {"score": 1.0}},
            "authenticity": {"authenticity": "pass", "reason": "string details"},
        }
        md_text, _ = _build_qa_gate_report(
            "k",
            product="p.md",
            kind="PROCESSED",
            delivered=False,
            quality="FAIL",
            gates=gates,
        )
        assert "| D1 | FAIL | err-text |" in md_text
        assert "| D2 | FAIL | why-text |" in md_text
        assert '"score"' in md_text
        assert "| D3 | PASS |" in md_text
        assert "| authenticity | PASS | string details |" in md_text


# ---------------------------------------------------------------------------
# write_gate_report
# ---------------------------------------------------------------------------


class TestWriteGateReport:
    def test_passing_product_writes_md_and_json_pair(self, tmp_path: Path) -> None:
        product = _passing_digest(tmp_path)
        out_dir = tmp_path / "01-QA-GATES"
        out_dir.mkdir()
        result = write_gate_report(out_dir, product, kind="PROCESSED")

        assert result["quality"] == "PASS"
        assert result["delivered"] is True
        assert result["key"].endswith("digest-2026-09-04")
        assert result["gates"]["D1"]["passed"] is True

        md_path: Path = result["md"]
        json_path: Path = result["json"]
        assert md_path.name == f"gate-report-{result['key']}.md"
        assert json_path.name == f"gate-report-{result['key']}.json"
        assert md_path.is_file() and json_path.is_file()
        assert md_path.read_text(encoding="utf-8").startswith("# Gate Report — ")
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["delivered"] is True
        assert payload["quality"] == "PASS"
        assert payload["product_key"] == result["key"]

    def test_failing_product_records_delivered_false(self, tmp_path: Path) -> None:
        product = _broken_report(tmp_path)
        out_dir = tmp_path / "01-QA-GATES"
        out_dir.mkdir()
        result = write_gate_report(out_dir, product, kind="PROCESSED")

        assert result["quality"] == "FAIL"
        assert result["delivered"] is False
        payload = json.loads(result["json"].read_text(encoding="utf-8"))
        assert payload["delivered"] is False
        assert payload["rejected_reason"].startswith("D1:")
        md_text = result["md"].read_text(encoding="utf-8")
        assert "- Delivered: no (rejected)" in md_text

    def test_default_kind_is_processed(self, tmp_path: Path) -> None:
        product = _passing_digest(tmp_path)
        out_dir = tmp_path / "gates"
        out_dir.mkdir()
        result = write_gate_report(out_dir, product)
        payload = json.loads(result["json"].read_text(encoding="utf-8"))
        assert payload["kind"] == "PROCESSED"
