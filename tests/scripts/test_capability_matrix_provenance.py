"""Issue #646: the capability matrix must not report L3 for KB-derived output.

``L3`` is documented as "verified end to end".  It used to be reachable when
every LLM call failed and the product was assembled deterministically from
the knowledge base: the matrix showed a *better* result precisely because the
model was broken.  These tests pin the separation:

- the generators record a provenance signal when a KB-derived fallback
  replaces LLM output;
- ``compute_layers`` refuses to report ``L3`` for a degraded artifact and
  reports ``L2-degraded`` instead (structure valid, not LLM-generated);
- a degraded cell is a failure for the run, never an honest block.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import capability_matrix as cm  # noqa: E402

import autoinfo.output as output  # noqa: E402
from tests._freshness import fresh_iso  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_provenance() -> Any:
    output.reset_llm_provenance()
    yield
    output.reset_llm_provenance()


class TestProvenanceRecorder:
    def test_default_is_llm_generated(self) -> None:
        state = output.llm_provenance()
        assert state["llm_generated"] is True
        assert state["kb_fallback_reasons"] == []

    def test_marking_a_fallback_flips_provenance(self) -> None:
        output.mark_kb_fallback("unit_test_reason")
        state = output.llm_provenance()
        assert state["llm_generated"] is False
        assert state["kb_fallback_reasons"] == ["unit_test_reason"]

    def test_reasons_are_deduplicated_and_sorted(self) -> None:
        output.mark_kb_fallback("b_reason")
        output.mark_kb_fallback("a_reason")
        output.mark_kb_fallback("b_reason")
        assert output.llm_provenance()["kb_fallback_reasons"] == ["a_reason", "b_reason"]

    def test_reset_clears_state(self) -> None:
        output.mark_kb_fallback("r")
        output.reset_llm_provenance()
        assert output.llm_provenance()["llm_generated"] is True


class TestComputeLayersDegraded:
    def test_l3_is_unreachable_for_kb_derived_artifact(self) -> None:
        verdict = cm.compute_layers(
            l1_pass=True, l2_passed=True, artifact_bytes=10_000, llm_generated=False
        )
        assert verdict.l2 is True
        assert verdict.l3 is False
        assert verdict.reached == "L2-degraded"

    def test_llm_generated_artifact_still_reaches_l3(self) -> None:
        verdict = cm.compute_layers(l1_pass=True, l2_passed=True, artifact_bytes=10_000)
        assert verdict.reached == "L3"

    def test_degraded_stays_below_a_failing_structure(self) -> None:
        verdict = cm.compute_layers(
            l1_pass=True, l2_passed=False, artifact_bytes=10_000, llm_generated=False
        )
        assert verdict.reached == "L1"

    def test_degraded_is_not_an_honest_block(self) -> None:
        assert "L2-degraded" not in cm.HONEST_BLOCKS


class TestMatrixRowRecordsProvenance:
    def _row(self, artifact: Path) -> dict[str, Any]:
        combo = SimpleNamespace(product="tutorial", format="markdown", gated=True, key="t")
        route = cm.Route(
            lambda _ctx: cm.GenerationCall(self._generate, {}, False), needs_template=False
        )
        with (
            patch.object(cm, "ROUTES", {"tutorial": route}),
            patch.object(cm, "check_l2", return_value={"passed": True, "checks": {}}),
            patch.object(cm, "write_artifact", return_value=artifact),
        ):
            return cm.generate_cell(
                combo,
                domain="medical-research",
                topic="",
                artifact_root=artifact.parent,
                force=True,
                keyed="keyed",
                llm_available=True,
            )

    @staticmethod
    def _generate(**_kwargs: Any) -> str:
        output.mark_kb_fallback("synthesis_empty")
        return "x" * 1000

    def test_degraded_cell_row_reports_l2_degraded(self, tmp_path: Path) -> None:
        artifact = tmp_path / "tutorial-markdown.md"
        artifact.write_text("x" * 1000, encoding="utf-8")
        row = self._row(artifact)
        assert row["reached"] == "L2-degraded"
        assert row["l3"] is False
        assert row["l2"] is True
        assert row["llm_generated"] is False
        assert row["provenance"] == "synthesis_empty"

    def test_clean_cell_row_still_reports_l3(self, tmp_path: Path) -> None:
        artifact = tmp_path / "tutorial-markdown.md"
        artifact.write_text("x" * 1000, encoding="utf-8")
        combo = SimpleNamespace(product="tutorial", format="markdown", gated=True, key="t")
        route = cm.Route(
            lambda _ctx: cm.GenerationCall(lambda **_: "x" * 1000, {}, False), needs_template=False
        )
        with (
            patch.object(cm, "ROUTES", {"tutorial": route}),
            patch.object(cm, "check_l2", return_value={"passed": True, "checks": {}}),
            patch.object(cm, "write_artifact", return_value=artifact),
        ):
            row = cm.generate_cell(
                combo,
                domain="medical-research",
                topic="",
                artifact_root=artifact.parent,
                force=True,
                keyed="keyed",
                llm_available=True,
            )
        assert row["reached"] == "L3"
        assert row["llm_generated"] is True

    def test_markdown_exposes_the_llm_column(self) -> None:
        row = {
            "domain": "d",
            "product": "tutorial",
            "format": "markdown",
            "gated": True,
            "keyed": "keyed",
            "reached": "L2-degraded",
            "l1": True,
            "l2": True,
            "l3": False,
            "duration_s": 1.0,
            "artifact": "a.md",
            "detail": "",
            "llm_generated": False,
            "provenance": "synthesis_empty",
        }
        meta = {
            "generated_at": "test-run",
            "domains": ["d"],
            "spec": "s",
            "keyed": "keyed",
            "command": "cmd",
        }
        md = cm.render_markdown(meta, [row])
        header = next(line for line in md.splitlines() if line.startswith("| Domain |"))
        assert "LLM" in header
        data_row = next(line for line in md.splitlines() if line.startswith("| d |"))
        assert "L2-degraded" in data_row
        assert "kb-derived" in data_row


class TestRealGeneratorsRecordFallback:
    """The seams record provenance through the real generator entry points."""

    _ENTRIES = [
        {
            "entry_id": "e1",
            "title": "Imaging in IVF",
            "summary": "Time-lapse imaging improves IVF outcomes markedly.",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/1/",
            "source_type": "api",
            "source_platform": "pubmed",
            "relevance_score": 90.0,
            "tags": "[]",
            "tier": "01-Raw",
            "language": "en",
            "collected_at": fresh_iso(1),
        }
    ]

    def test_tutorial_kb_fallback_marks_provenance(self) -> None:
        from autoinfo.output import generate_tutorial

        entries = [dict(self._ENTRIES[0], collected_at=fresh_iso(1))]
        with (
            patch("autoinfo.output.KBStore") as mock_kb,
            patch("autoinfo.output._call_llm_for_tutorial", return_value={}),
        ):
            mock_kb.return_value.list_entries.return_value = entries
            generate_tutorial(domain="medical-research", format="markdown")

        state = output.llm_provenance()
        assert state["llm_generated"] is False
        assert "tutorial_llm_unusable" in state["kb_fallback_reasons"]

    def test_tutorial_with_llm_output_stays_clean(self) -> None:
        from autoinfo.output import generate_tutorial

        entries = [dict(self._ENTRIES[0], collected_at=fresh_iso(1))]
        llm_payload = {
            "title": "Imaging in IVF",
            "duration": "10 min",
            "objectives": ["Explain time-lapse imaging", "Compare IVF outcomes"],
            "content": "Time-lapse imaging improves live birth rates.",
            "summary": "A short summary of the tutorial.",
            "exercises": [{"title": "Review", "description": "Summarize the findings."}],
        }
        with (
            patch("autoinfo.output.KBStore") as mock_kb,
            patch("autoinfo.output._call_llm_for_tutorial", return_value=llm_payload),
        ):
            mock_kb.return_value.list_entries.return_value = entries
            generate_tutorial(domain="medical-research", format="markdown")

        assert output.llm_provenance()["llm_generated"] is True
