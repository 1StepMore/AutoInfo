"""Tests for the AC5 director-review DRAFT module.

The module produces a machine DRAFT of the AC5 (quality) director sampling
review (``docs/dev/acceptance-framework.md`` §5.2).  Its non-negotiable
property is the RISK ceiling: a correct model verdict of PASS is coerced to
RISK, so a rubber stamp is structurally impossible; an unreachable or
unparseable model is ESCALATE; the draft is never a director verdict and never
an acceptance verdict.

These tests mirror the fail-loud discipline of
``tests/scripts/test_agent_review_battery.py`` and the
``regression-battery-verdict-parse`` scenario: no network, no real model —
the judgment channel is mocked and the real inherited machinery is exercised.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

# scripts/agent_review/ is not a package — load it via sys.path (same trick
# the battery test uses).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "agent_review"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "src"))

import ac5_director_review as ac5  # noqa: E402

_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "known-defects"
_DEFECT_DIR = _FIXTURES / "ac5-review"
_CLEAN_DIR = _FIXTURES / "ac5-review-clean"


# ---------------------------------------------------------------------------
# LLM-shaped response stubs (mirror test_agent_review_battery.py)
# ---------------------------------------------------------------------------


class _Msg:
    def __init__(self, content: Any) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: Any, finish_reason: str = "stop") -> None:
        self.message = _Msg(content)
        self.finish_reason = finish_reason


class _Resp:
    def __init__(self, content: Any, finish_reason: str = "stop") -> None:
        self.choices = [_Choice(content, finish_reason)]


def _markdown_block(verdict: str, evidence: str = "magazine-digest.md:18") -> str:
    return (
        "## Verdict\n"
        "- **blind_spot**: ac5-quality\n"
        f"- **verdict**: {verdict}\n"
        f"- **evidence**: {evidence}\n"
        "- **note**: judged against the four quality concerns\n"
    )


def _worklist_item() -> dict[str, str]:
    path = _DEFECT_DIR / "magazine-digest.md"
    return {"family": "magazine-digest", "file": path.name, "path": str(path)}


def _review(
    resp: Any,
    *,
    want_json: bool = False,
    semantic: bool = True,
) -> dict[str, Any]:
    """Run the REAL review with the channel mocked to return *resp*."""
    with patch("autoinfo.llm.call_with_fallback", return_value=resp):
        with patch.object(ac5, "_channel_json_capable", return_value=want_json):
            return ac5.review_product(_worklist_item(), semantic=semantic)


# ---------------------------------------------------------------------------
# THE INVARIANT: coerce_to_draft (total, pure, never PASS)
# ---------------------------------------------------------------------------


def test_coerce_to_draft_maps_every_recognised_token_to_the_risk_ceiling() -> None:
    assert ac5.coerce_to_draft("PASS") == "RISK"
    assert ac5.coerce_to_draft("FLAG") == "RISK"
    assert ac5.coerce_to_draft("RISK") == "RISK"


def test_coerce_to_draft_preserves_escalate() -> None:
    assert ac5.coerce_to_draft("ESCALATE") == "ESCALATE"


def test_coerce_to_draft_is_total_and_never_returns_pass() -> None:
    samples = [
        "PASS",
        "pass",
        "  PASS  ",
        "**PASS**",
        "PASS\n",
        "FLAG",
        "flag",
        "ESCALATE",
        "escalate",
        "RISK",
        "risk",
        "PASSING",
        "garbage",
        "",
        "0",
        "None",
        "not a verdict",
    ]
    for raw in samples:
        assert ac5.coerce_to_draft(raw) != "PASS", f"{raw!r} mapped to PASS"


def test_coerce_to_draft_unknown_input_escalates() -> None:
    assert ac5.coerce_to_draft("totally unrelated prose") == "ESCALATE"
    assert ac5.coerce_to_draft("") == "ESCALATE"


# ---------------------------------------------------------------------------
# Fail-loud floor: unreachable / unparseable / truncated -> ESCALATE
# ---------------------------------------------------------------------------


def test_unreachable_llm_escalates_never_risk_or_pass() -> None:
    with patch("autoinfo.llm.call_with_fallback", side_effect=RuntimeError("provider down")):
        with patch.object(ac5, "_channel_json_capable", return_value=False):
            res = ac5.review_product(_worklist_item(), semantic=True)
    assert res["llm_verdict"] == "ESCALATE"
    assert res["draft_verdict"] == "ESCALATE"


def test_garbage_unparseable_output_escalates() -> None:
    res = _review(_Resp("totally unrelated prose with no verdict block"))
    assert res["draft_verdict"] == "ESCALATE"


def test_truncated_output_escalates_with_truncation_note() -> None:
    resp = _Resp("## Verdict\n- **blind_spot**: x\n- **verdict**: PA", finish_reason="length")
    res = _review(resp)
    assert res["draft_verdict"] == "ESCALATE"
    assert "trunc" in res["note"].lower()


def test_json_mode_garbage_escalates() -> None:
    res = _review(_Resp("{broken json"), want_json=True)
    assert res["draft_verdict"] == "ESCALATE"


# ---------------------------------------------------------------------------
# THE HEADLINE: a valid model PASS is coerced to RISK on the way out
# ---------------------------------------------------------------------------


def test_valid_model_pass_is_coerced_to_risk() -> None:
    res = _review(_Resp(_markdown_block("PASS")))
    assert res["llm_verdict"] == "PASS"
    assert res["draft_verdict"] == "RISK"


def test_valid_model_flag_is_coerced_to_risk() -> None:
    res = _review(_Resp(_markdown_block("FLAG")))
    assert res["llm_verdict"] == "FLAG"
    assert res["draft_verdict"] == "RISK"


def test_valid_model_escalate_stays_escalate() -> None:
    res = _review(_Resp(_markdown_block("ESCALATE")))
    assert res["llm_verdict"] == "ESCALATE"
    assert res["draft_verdict"] == "ESCALATE"


def test_json_mode_pass_payload_is_risk_and_requests_json_mode() -> None:
    payload = json.dumps(
        {"verdict": "PASS", "evidence": "magazine-digest.md:18", "note": "looks fine"}
    )
    with patch("autoinfo.llm.call_with_fallback", return_value=_Resp(payload)) as mock_call:
        with patch.object(ac5, "_channel_json_capable", return_value=True):
            res = ac5.review_product(_worklist_item(), semantic=True)
    assert res["draft_verdict"] == "RISK"
    assert mock_call.call_args.kwargs.get("json_mode") is True


def test_missing_evidence_is_never_a_risk_pass_through() -> None:
    """A recognised verdict with no evidence is inadmissible -> ESCALATE."""
    resp = _Resp(
        "## Verdict\n- **blind_spot**: x\n- **verdict**: PASS\n- **evidence**:\n"
        "- **note**: adjacent line\n"
    )
    res = _review(resp)
    assert res["draft_verdict"] == "ESCALATE"


# ---------------------------------------------------------------------------
# semantic=False never touches the LLM; preview row is RISK
# ---------------------------------------------------------------------------


def test_semantic_false_does_not_call_llm_and_emits_risk() -> None:
    with patch("autoinfo.llm.call_with_fallback") as mock_call:
        with patch.object(ac5, "_channel_json_capable", return_value=True):
            res = ac5.review_product(_worklist_item(), semantic=False)
            mock_call.assert_not_called()
    assert res["draft_verdict"] == "RISK"
    assert res["llm_verdict"] == "NOT_REVIEWED"
    assert "not requested" in res["note"].lower()
    assert set(res.keys()) == {
        "family",
        "file",
        "draft_verdict",
        "llm_verdict",
        "evidence",
        "note",
    }


# ---------------------------------------------------------------------------
# Worklist assembly: manifest PROCESSED entries, else *.md scan
# ---------------------------------------------------------------------------


def test_worklist_from_manifest_includes_only_processed(tmp_path: Path) -> None:
    proc = tmp_path / "02-PROCESSED" / "ai-commercial"
    proc.mkdir(parents=True)
    (proc / "magazine-digest.md").write_text("# m\n", encoding="utf-8")
    manifest = {
        "files": [
            {
                "file": "02-PROCESSED/ai-commercial/magazine-digest.md",
                "kind": "PROCESSED",
                "source": "s",
                "size": 4,
                "gates": {},
                "quality": "PASS",
            },
            {
                "file": "01-Raw/x.json",
                "kind": "RAW",
                "source": "s",
                "size": 2,
                "gates": {},
                "quality": "PASS",
            },
        ],
        "rejected": [],
        "ux": None,
        "qa_gate_reports": [],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    items = ac5.build_ac5_worklist(tmp_path)
    assert len(items) == 1
    item = items[0]
    assert set(item.keys()) == {"family", "file", "path"}
    assert item["family"] == "magazine-digest"
    assert item["file"] == "magazine-digest.md"
    assert Path(item["path"]).name == "magazine-digest.md"
    assert Path(item["path"]).exists()


def test_worklist_falls_back_to_md_scan_without_manifest(tmp_path: Path) -> None:
    (tmp_path / "digest.md").write_text("# d\n", encoding="utf-8")
    (tmp_path / "magazine-digest.md").write_text("# m\n", encoding="utf-8")
    items = ac5.build_ac5_worklist(tmp_path)
    assert {i["family"] for i in items} == {"digest", "magazine-digest"}
    assert all(Path(i["path"]).exists() for i in items)


# ---------------------------------------------------------------------------
# run_ac5_review: summary.passed is ALWAYS 0
# ---------------------------------------------------------------------------


def test_run_preview_summary_passed_is_zero() -> None:
    report = ac5.run_ac5_review(_CLEAN_DIR, semantic=False)
    assert report["summary"]["passed"] == 0
    assert report["summary"]["risk"] == report["summary"]["total"]
    assert report["summary"]["escalate"] == 0
    assert report["honesty"]["reviewed"] == []
    assert report["honesty"]["not_reviewed"]


def test_run_semantic_summary_passed_is_zero_even_on_model_pass() -> None:
    with patch("autoinfo.llm.call_with_fallback", return_value=_Resp(_markdown_block("PASS"))):
        with patch.object(ac5, "_channel_json_capable", return_value=False):
            report = ac5.run_ac5_review(_CLEAN_DIR, semantic=True)
    assert report["summary"]["passed"] == 0
    assert report["summary"]["risk"] == report["summary"]["total"]
    assert report["honesty"]["reviewed"]


# ---------------------------------------------------------------------------
# Fixtures: clean product still RISK under a mocked PASS (no rubber stamp)
# ---------------------------------------------------------------------------


def test_clean_fixture_mocked_pass_still_risk() -> None:
    items = ac5.build_ac5_worklist(_CLEAN_DIR)
    assert items
    with patch("autoinfo.llm.call_with_fallback", return_value=_Resp(_markdown_block("PASS"))):
        with patch.object(ac5, "_channel_json_capable", return_value=False):
            res = ac5.review_product(items[0], semantic=True)
    assert res["draft_verdict"] == "RISK"


def test_defect_fixture_mocked_pass_still_risk() -> None:
    items = ac5.build_ac5_worklist(_DEFECT_DIR)
    assert items
    with patch("autoinfo.llm.call_with_fallback", return_value=_Resp(_markdown_block("PASS"))):
        with patch.object(ac5, "_channel_json_capable", return_value=False):
            res = ac5.review_product(items[0], semantic=True)
    assert res["draft_verdict"] == "RISK"


# ---------------------------------------------------------------------------
# Persistence is runtime state, never under docs/
# ---------------------------------------------------------------------------


def test_persist_writes_runtime_state_not_docs(tmp_path: Path) -> None:
    report = ac5.run_ac5_review(_CLEAN_DIR, semantic=False)
    out = ac5._persist(report, "v-test", tmp_path)
    assert out.exists()
    assert out.parent.name == "ac5-draft"
    assert out.name.startswith("ac5-draft-")
    assert "docs" not in out.parts
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["version"] == "v-test"
    assert payload["report"]["summary"]["passed"] == 0


# ---------------------------------------------------------------------------
# CLI: exit 1 on any ESCALATE, else 0
# ---------------------------------------------------------------------------


def test_main_preview_returns_zero(tmp_path: Path) -> None:
    rc = ac5.main(["--delivery-dir", str(_CLEAN_DIR), "--out", str(tmp_path), "--json"])
    assert rc == 0


def test_main_escalate_returns_one(tmp_path: Path) -> None:
    with patch("autoinfo.llm.call_with_fallback", side_effect=RuntimeError("provider down")):
        with patch.object(ac5, "_channel_json_capable", return_value=False):
            rc = ac5.main(
                [
                    "--delivery-dir",
                    str(_CLEAN_DIR),
                    "--semantic",
                    "--out",
                    str(tmp_path),
                    "--json",
                ]
            )
    assert rc == 1


def test_ac5_prompt_uses_shared_verdict_schema() -> None:
    """The AC5 judge must speak battery's verdict schema, not a private copy (#426).

    ac5 used to inline its own copy of the `## Verdict` block and had drifted:
    it dropped the trailing "Do not add prose before or after it." sentence, so
    the two judges disagreed about what a well-formed reply looks like. The
    constant is now shared, and this test fails if ac5 ever re-inlines it.
    """
    import battery  # noqa: PLC0415

    prompt = ac5._ac5_prompt(
        {
            "family": "magazine-digest",
            "file": "m.md",
            "path": str(_CLEAN_DIR / "magazine-digest.md"),
        }
    )

    assert battery._VERDICT_SCHEMA_BLOCK in prompt, "ac5 must embed the shared schema block"
    assert "Do not add prose" in prompt, "ac5 lost the shared block's trailing sentence"


def test_verdict_schema_defined_once_across_judges() -> None:
    """Only battery may define the schema; ac5 must import, not restate it."""

    ac5_src = (_REPO_ROOT / "scripts" / "agent_review" / "ac5_director_review.py").read_text(
        encoding="utf-8"
    )
    assert "OUTPUT SCHEMA" not in ac5_src, "ac5 re-inlined the schema instead of importing it"
    assert ac5_src.count("_VERDICT_SCHEMA_BLOCK") == 2, "expected one import + one use"
