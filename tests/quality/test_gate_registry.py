"""Unified gate registry + unified retry semantics (issue #583)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from autoinfo.config import _GATE_CONFIG_KEY_MAP, QualityGateConfig
from autoinfo.models import ExtractionResult, Item
from autoinfo.quality import (
    QUALITY_GATE_ORDER,
    D1ProductCompleteness,
    D2FormatIntegrity,
    D3Freshness,
    G0SchemaIntegrity,
    G1SourceAuthority,
    G1TosCompliance,
    G2Dedup,
    G3RelevanceScoring,
    G4FactualConsistency,
    G5TranslationAccuracy,
    G7EntityFactConsistency,
    GateContext,
    retry_with_escalation,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SPEC = REPO_ROOT / "docs" / "dev" / "specs" / "quality-gates.md"
CATALOG_HEADING = "## 3. Gate Catalog"


#: Catalog-row labels that are not already gate config keys.
_DOC_LABELS: dict[str, str] = {
    **_GATE_CONFIG_KEY_MAP,
    "G1-ToS": "G1-TosCompliance",
}


def _documented_gate_order() -> list[str]:
    """Parse the gate-catalog table into its row order (long gate names)."""
    lines = GATE_SPEC.read_text(encoding="utf-8").splitlines()
    assert CATALOG_HEADING in lines, f"{GATE_SPEC} is missing {CATALOG_HEADING!r}"
    start = lines.index(CATALOG_HEADING) + 1

    rows: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("|"):
            rows.append(stripped)
        elif rows:
            break
    assert len(rows) >= 3, f"no catalog rows found under {CATALOG_HEADING!r}"

    order: list[str] = []
    for row in rows[2:]:
        first_cell = row.strip("|").split("|")[0].strip()
        name = first_cell.replace("**", "").split(":")[0].strip()
        order.append(_DOC_LABELS.get(name, name))
    return order


def _make_item(item_id: str = "reg-item") -> Item:
    return Item(
        id=item_id,
        source_name="pubmed",
        source_type="api",
        source_platform="pubmed",
        source_url=f"https://example.com/{item_id}",
        title="An IVF study",
        content="IVF outcomes improved with time-lapse imaging.",
        content_type="text",
        collected_at="2026-07-15T10:00:00Z",
        language="en",
        domain="medical-research",
        quality_tier=1,
    )


def test_registry_order_matches_gate_catalog_document() -> None:
    """QUALITY_GATE_ORDER must equal the documented gate-catalog row order."""
    documented = _documented_gate_order()
    documented_quality = [name for name in documented if name in QUALITY_GATE_ORDER]
    assert list(QUALITY_GATE_ORDER) == documented_quality, (
        "quality-gate execution order drifted from docs/dev/specs/quality-gates.md:\n"
        f"  registry: {QUALITY_GATE_ORDER}\n  doc:      {documented_quality}"
    )


def test_every_gate_exposes_one_ctx_entry_point() -> None:
    """Every gate has exactly one public check taking a context object first."""
    gates = (
        G0SchemaIntegrity(),
        G1SourceAuthority(),
        G1TosCompliance(),
        G2Dedup(),
        G3RelevanceScoring(),
        G4FactualConsistency(model="test/model"),
        G5TranslationAccuracy(model="test/model"),
        G7EntityFactConsistency(),
        D1ProductCompleteness(),
        D2FormatIntegrity(),
        D3Freshness(),
    )
    for gate in gates:
        params = list(inspect.signature(gate.check).parameters)
        assert params[:1] == ["ctx"], f"{type(gate).__name__}.check must start with ctx"
        assert isinstance(gate.gate_name, str) and gate.gate_name
        assert gate.category in {"hard", "soft", "delivery"}


def test_retry_helper_semantics() -> None:
    """retries counts EXTRA attempts: total = 1 + retries."""
    calls: list[int] = []

    def _always_fail(attempt: object) -> None:
        calls.append(1)
        return None

    value, attempts = retry_with_escalation(_always_fail, retries=3)
    assert value is None
    assert attempts == 4
    assert len(calls) == 4

    calls.clear()
    retry_with_escalation(_always_fail, retries=0)
    assert len(calls) == 1


def test_g0_retries_zero_makes_exactly_one_attempt() -> None:
    """G0 retries=0 → one deterministic attempt, retry_count=0."""
    g0 = G0SchemaIntegrity()
    result = g0.check(
        GateContext(
            raw_item={"source_url": "", "source_type": "", "source_platform": ""},
            gate_config=QualityGateConfig(name="G0", category="hard", retries=0),
        )
    )
    assert result.passed is False
    assert result.details["retry_count"] == 0
    assert result.details["attempts"] == 1


def test_g4_retries_three_makes_exactly_four_attempts(tmp_path: Path) -> None:
    """G4 retries=3 → 1 + 3 = 4 LLM calls before blocking."""
    item = _make_item("g4-attempts")
    extraction = ExtractionResult(item_id=item.id, tl_dr="IVF outcomes improved.")
    gate_config = QualityGateConfig(
        name="G4",
        category="hard",
        retries=3,
        retry_models=["test/model-two"],
        action="block",
    )

    def _contradiction(*args: object, **kwargs: object) -> MagicMock:
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = json.dumps(
            {"contradiction": True, "explanation": "contradicts the source"}
        )
        return response

    with patch("autoinfo.quality.call_with_fallback", side_effect=_contradiction) as mock_cwf:
        g4 = G4FactualConsistency(model="test/model", collections_path=tmp_path)
        result = g4.check(item, extraction, gate_config=gate_config)

    assert result.passed is False
    assert result.details["action"] == "block"
    assert result.details["retry_count"] == 4
    assert mock_cwf.call_count == 4


def test_g0_counts_exactly_one_invocation_per_item() -> None:
    """The process pipeline must not re-run G0 inside run_quality_gates."""
    from tests.quality.test_g0_once import run_pipeline_with_counted_g0

    assert run_pipeline_with_counted_g0("ok") == 1
    assert run_pipeline_with_counted_g0("blocked") == 1
