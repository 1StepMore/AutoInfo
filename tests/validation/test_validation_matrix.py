"""Domain-matrix scenario parameterization tests (issue #280).

Locks the ``matrix_domains`` scenario schema key: when present,
``run_scenario`` executes the scenario once per listed domain, deep-
substituting ``{{domain}}`` in every ``kind: mcp`` step's ``arguments``
(recursively through nested dicts/lists), and aggregates the sub-runs
ALL-or-nothing.  Scenarios WITHOUT the key must behave byte-identically
to the pre-matrix harness — one execution, no substitution, no ``matrix``
key in the result envelope.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

from autoinfo.mcp import validation as v
from autoinfo.validation_matrix import (
    _is_formulaic_fallback,
    _is_weak_analysis,
    _so_what_substantive,
)

MATRIX_YAML = """\
name: matrix-scenario
description: "Domain-matrix fixture"
category: happy_path
requires_env: []
matrix_domains: ["ai-commercial", "b2b"]
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "schema per domain"
    tool: get_domain_schema
    kind: mcp
    arguments:
      domain: "{{domain}}"
      nested:
        x: "{{domain}}"
      list:
        - "{{domain}}"
    expect:
      success: true
"""

PLAIN_YAML = """\
name: plain-scenario
description: "No-matrix fixture (zero-regression guard)"
category: happy_path
requires_env: []
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "schema per domain"
    tool: get_domain_schema
    arguments:
      domain: "{{domain}}"
      nested:
        x: "{{domain}}"
      list:
        - "{{domain}}"
    expect:
      success: true
"""

PARTIAL_YAML = """\
name: partial-scenario
description: "Partial substitution fixture"
category: happy_path
requires_env: []
matrix_domains: ["ai-commercial"]
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "partial substitution"
    tool: get_domain_schema
    arguments:
      domain: "{{domain}}"
      label: "domain-matrix-check"
      path: "https://{{domain}}.example.com/rss"
      list:
        - "plain-string"
        - "{{domain}}-report"
    expect:
      success: true
"""

UNION_YAML = """\
name: union-scenario
description: "Union gate fixture"
category: happy_path
requires_env: []
requires_domain: ["medical-research"]
matrix_domains: ["ai-commercial", "b2b"]
pyramid_layer: component
pipeline_stage: A7
user_level: B2.5
steps:
  - name: "schema per domain"
    tool: get_domain_schema
    arguments:
      domain: "{{domain}}"
    expect:
      success: true
"""


def _write_scenario(tmp_path: Path, body: str) -> Path:
    sd = tmp_path / "scenarios"
    sd.mkdir(exist_ok=True)
    (sd / "fixture.yaml").write_text(body, encoding="utf-8")
    return sd


def _scenario_body(**extra: Any) -> str:
    data: dict[str, Any] = {
        "name": "schema-scenario",
        "description": "schema fixture",
        "category": "happy_path",
        "pyramid_layer": "component",
        "pipeline_stage": "A7",
        "user_level": "B2.4",
        "steps": [
            {
                "name": "s",
                "tool": "t",
                "arguments": {},
                "expect": {"success": True},
            }
        ],
    }
    data.update(extra)
    return yaml.safe_dump(data)


class _CapturingDispatch:
    """Stub dispatch recording every (tool, arguments) call.

    Fails (success=false) when the resolved ``domain`` argument is in
    ``fail_domains`` so sub-run aggregation can be exercised.
    """

    def __init__(self, fail_domains: set[str] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._fail = fail_domains or set()

    async def __call__(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((tool, dict(arguments)))
        if arguments.get("domain") in self._fail:
            return {
                "success": False,
                "error": {"code": "DOMAIN_NOT_FOUND", "message": "no such domain"},
            }
        return {"success": True, "data": {"ok": True}}


class TestRunScenarioMatrix:
    """run_scenario domain-matrix expansion."""

    async def test_matrix_expands_once_per_domain_with_deep_substitution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each member domain fires the step once, ``{{domain}}`` replaced
        everywhere — top-level, nested dicts, and list items."""
        monkeypatch.setattr(v, "_configured_domain_names", lambda: ["ai-commercial", "b2b"])
        sd = _write_scenario(tmp_path, MATRIX_YAML)
        dispatch = _CapturingDispatch()

        result = await v.run_scenario("matrix-scenario", dispatch=dispatch, scenarios_dir=sd)

        assert [tool for tool, _ in dispatch.calls] == [
            "get_domain_schema",
            "get_domain_schema",
        ]
        expected_args = {
            "ai-commercial": {
                "domain": "ai-commercial",
                "nested": {"x": "ai-commercial"},
                "list": ["ai-commercial"],
            },
            "b2b": {
                "domain": "b2b",
                "nested": {"x": "b2b"},
                "list": ["b2b"],
            },
        }
        assert {args["domain"] for _, args in dispatch.calls} == {
            "ai-commercial",
            "b2b",
        }
        for _, args in dispatch.calls:
            assert args == expected_args[args["domain"]]

        assert result["status"] == "passed"
        assert result["summary"]["total"] == 2
        assert result["summary"]["passed"] == 2
        assert [s["domain"] for s in result["steps"]] == ["ai-commercial", "b2b"]
        matrix = result["matrix"]
        assert matrix["domains"] == ["ai-commercial", "b2b"]
        assert set(matrix["per_domain"]) == {"ai-commercial", "b2b"}
        for domain in matrix["domains"]:
            sub = matrix["per_domain"][domain]
            assert sub["status"] == "passed"
            assert sub["summary"]["total"] == 1
            assert sub["summary"]["passed"] == 1

    async def test_without_matrix_domains_dispatches_exactly_once(self, tmp_path: Path) -> None:
        """Zero-regression guard: no matrix key -> one execution, no
        substitution (the literal ``{{domain}}`` token arrives untouched),
        and the envelope carries no ``matrix`` key."""
        sd = _write_scenario(tmp_path, PLAIN_YAML)
        dispatch = _CapturingDispatch()

        result = await v.run_scenario("plain-scenario", dispatch=dispatch, scenarios_dir=sd)

        assert len(dispatch.calls) == 1
        assert dispatch.calls[0][0] == "get_domain_schema"
        assert dispatch.calls[0][1] == {
            "domain": "{{domain}}",
            "nested": {"x": "{{domain}}"},
            "list": ["{{domain}}"],
        }
        assert "matrix" not in result
        assert result["status"] == "passed"
        assert result["summary"]["total"] == 1

    async def test_partial_substitution_keeps_sibling_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only the exact ``{{domain}}`` token is replaced — the substituted
        value must never appear inside a non-placeholder string (e.g. the
        word 'domain' in 'domain-matrix-check' must survive untouched)."""
        monkeypatch.setattr(v, "_configured_domain_names", lambda: ["ai-commercial"])
        sd = _write_scenario(tmp_path, PARTIAL_YAML)
        dispatch = _CapturingDispatch()

        result = await v.run_scenario("partial-scenario", dispatch=dispatch, scenarios_dir=sd)

        args = dispatch.calls[0][1]
        assert args["domain"] == "ai-commercial"
        assert args["label"] == "domain-matrix-check"
        assert args["path"] == "https://ai-commercial.example.com/rss"
        assert args["list"] == ["plain-string", "ai-commercial-report"]
        assert result["status"] == "passed"

    async def test_matrix_failure_fails_scenario_with_per_domain_results(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Aggregation is ALL-or-nothing: one failing sub-run fails the whole
        scenario, with every sub-run's result recorded per domain."""
        monkeypatch.setattr(v, "_configured_domain_names", lambda: ["ai-commercial", "b2b"])
        sd = _write_scenario(tmp_path, MATRIX_YAML)
        dispatch = _CapturingDispatch(fail_domains={"b2b"})

        result = await v.run_scenario("matrix-scenario", dispatch=dispatch, scenarios_dir=sd)

        assert result["status"] == "failed"
        assert result["summary"]["failed"] == 1
        assert result["summary"]["passed"] == 1
        assert result["matrix"]["per_domain"]["ai-commercial"]["status"] == "passed"
        assert result["matrix"]["per_domain"]["b2b"]["status"] == "failed"
        # the failing sub-run's step keeps its failed status with detail
        b2b_steps = result["matrix"]["per_domain"]["b2b"]["steps"]
        assert b2b_steps[0]["status"] == "failed"

    async def test_matrix_members_join_requires_domain_gate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Effective requires_domain is the union of the declared domains and
        the matrix members: a member missing from the project config gates the
        whole scenario unconfigured (no dispatch), all present -> runs."""
        monkeypatch.setattr(
            v, "_configured_domain_names", lambda: ["medical-research", "ai-commercial"]
        )
        sd = _write_scenario(tmp_path, UNION_YAML)
        dispatch = _CapturingDispatch()

        result = await v.run_scenario("union-scenario", dispatch=dispatch, scenarios_dir=sd)
        assert result["status"] == "unconfigured"
        assert "b2b" in result.get("unconfigured_reason", "")
        assert dispatch.calls == []

        monkeypatch.setattr(
            v,
            "_configured_domain_names",
            lambda: ["medical-research", "ai-commercial", "b2b"],
        )
        result = await v.run_scenario("union-scenario", dispatch=dispatch, scenarios_dir=sd)
        assert result["status"] == "passed"
        assert len(dispatch.calls) == 2


class TestLoadScenariosMatrixSchema:
    """load_scenarios schema validation for the matrix_domains key."""

    @pytest.mark.parametrize(
        "bad",
        [[], "ai-commercial", [123], [""], ["ai-commercial", 7]],
    )
    def test_load_scenarios_rejects_invalid_matrix_domains(self, tmp_path: Path, bad: Any) -> None:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "bad.yaml").write_text(_scenario_body(matrix_domains=bad), encoding="utf-8")
        with pytest.raises(ValueError, match="matrix_domains"):
            v.load_scenarios(sd)

    def test_load_scenarios_defaults_matrix_domains_to_empty(self, tmp_path: Path) -> None:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "plain.yaml").write_text(_scenario_body(), encoding="utf-8")
        scs = v.load_scenarios(sd)
        assert scs[0]["matrix_domains"] == []

    def test_load_scenarios_accepts_matrix_domains(self, tmp_path: Path) -> None:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "mat.yaml").write_text(
            _scenario_body(matrix_domains=["ai-commercial", "b2b"]),
            encoding="utf-8",
        )
        scs = v.load_scenarios(sd)
        assert scs[0]["matrix_domains"] == ["ai-commercial", "b2b"]


class TestListScenariosMatrix:
    """list_scenarios surfaces matrix_domains per scenario."""

    def test_list_scenarios_surfaces_matrix_domains(self, tmp_path: Path) -> None:
        sd = tmp_path / "scenarios"
        sd.mkdir()
        (sd / "mat.yaml").write_text(
            _scenario_body(name="mat-scenario", matrix_domains=["b2b"]),
            encoding="utf-8",
        )
        (sd / "plain.yaml").write_text(_scenario_body(name="plain-scenario"), encoding="utf-8")
        summary = {s["name"]: s for s in v.list_scenarios(sd)["scenarios"]}
        assert summary["mat-scenario"]["matrix_domains"] == ["b2b"]
        assert summary["plain-scenario"]["matrix_domains"] == []


# ---------------------------------------------------------------------------
# #947 — formulaic-fallback verdict requires prefix AND no concrete anchor.
# A formulaic opener only makes the field weak when the sentence carries no
# concrete object; concrete entities, numbers or citations mean a real
# analysis.
# ---------------------------------------------------------------------------

ISSUE_SENTENCE = (
    "Track Anthropic's quarterly public reporting regarding its compute "
    "commitments and infrastructure reliance on partners like Amazon and "
    "Google to gauge the long-term sustainability of its financing approach."
)


class TestIsWeakAnalysisFormulaicAnchor:
    """``_is_weak_analysis`` fourth rule: formulaic prefix alone is not weak
    when the sentence carries a concrete anchor (#947)."""

    @pytest.mark.parametrize(
        "text",
        [
            "Track developments in this domain over the coming quarters.",
            "Monitor developments around this space and keep an eye on how it evolves.",
            "Uncertain trajectory for this segment and its near-term outlook.",
        ],
    )
    def test_formulaic_without_anchor_stays_weak(self, text: str) -> None:
        """Formulaic openers with no digit/URL/citation/proper noun remain
        weak."""
        assert len(text) >= 40
        assert _is_weak_analysis(text)
        assert _is_formulaic_fallback(text)

    @pytest.mark.parametrize(
        "text",
        [
            # the exact sentence from the issue (proper-noun anchor)
            ISSUE_SENTENCE,
            # digit anchor
            "Track the 2027 renewal date in the contract.",
            # citation anchor
            "Monitor developments around the EU AI Act per [Source: commission release].",
            # URL anchor
            "Track the model changelog published at https://example.com/changelog each week.",
        ],
    )
    def test_formulaic_with_anchor_is_not_weak(self, text: str) -> None:
        assert len(text) >= 40
        assert not _is_weak_analysis(text)
        assert not _is_formulaic_fallback(text)

    def test_non_formulaic_prefix_unaffected(self) -> None:
        """The first three rules (empty/placeholder/<40) are unchanged."""
        assert _is_weak_analysis("")
        assert _is_weak_analysis("_No actions available._")
        assert _is_weak_analysis("too short")
        # a substantive non-formulaic sentence passes
        assert not _is_weak_analysis(
            "Anthropic's financing relies on partner compute commitments, "
            "which shapes its long-term sustainability."
        )


def _premium_briefing_markdown(actions: str) -> str:
    return (
        "# Premium Briefing\n\n"
        "## Key Takeaways\n\n"
        "### 1. Anthropic financing model\n\n"
        "> **So what**: Anthropic relies on partner-provided compute, which "
        "shapes its long-term financing sustainability.\n\n"
        "**Risk / Opportunity:** Financing concentration risk — dependence "
        "on partner compute commitments.\n\n"
        f"**Actions:** {actions}\n\n"
        "## References\n\n"
        "- [Source: example](https://example.com)\n"
    )


class TestSoWhatSubstantiveEndToEnd947:
    """``_so_what_substantive`` end-to-end on a synthetic premium-briefing
    with the #947 sentence (must pass) vs a bare formulaic action (must
    fail)."""

    def test_issue_sentence_passes(self) -> None:
        result = _so_what_substantive(
            _premium_briefing_markdown(ISSUE_SENTENCE), "ai-commercial", "premium-briefing"
        )
        assert result.passed is True, result.details

    def test_bare_formulaic_action_fails(self) -> None:
        result = _so_what_substantive(
            _premium_briefing_markdown("Track developments in this domain over the coming quarters."),
            "ai-commercial",
            "premium-briefing",
        )
        assert result.passed is False
        assert "takeaway 1 actions is weak" in result.details
