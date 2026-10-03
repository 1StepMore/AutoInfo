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
#: A delivery package shaped like the real one: a manifest whose PROCESSED set
#: mixes one reviewable ``.md`` product with a ``.log``, a ``.err``, an ``.mp4``
#: (real ftyp magic bytes), a ``.zip`` (real PK magic bytes) and a ``.json``.
#: The 5-file synthetic fixtures above could not raise UnicodeDecodeError, so
#: the binary-artifact class of defect was invisible to them.
_MIXED_DIR = _FIXTURES / "ac5-review-mixed"


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

    item = {
        "family": "magazine-digest",
        "file": "m.md",
        "path": str(_CLEAN_DIR / "magazine-digest.md"),
    }
    snippet = ac5._read_product_snippet(item["path"]).text
    prompt = ac5._ac5_prompt(item, snippet)

    assert battery._VERDICT_SCHEMA_BLOCK in prompt, "ac5 must embed the shared schema block"
    assert "Do not add prose" in prompt, "ac5 lost the shared block's trailing sentence"


def test_verdict_schema_defined_once_across_judges() -> None:
    """Only battery may define the schema; ac5 must import, not restate it."""

    ac5_src = (_REPO_ROOT / "scripts" / "agent_review" / "ac5_director_review.py").read_text(
        encoding="utf-8"
    )
    assert "OUTPUT SCHEMA" not in ac5_src, "ac5 re-inlined the schema instead of importing it"
    assert ac5_src.count("_VERDICT_SCHEMA_BLOCK") == 2, "expected one import + one use"


# ---------------------------------------------------------------------------
# Defect A — non-product artifacts must not reach the judge
#
# Real delivery package: 474 PROCESSED manifest entries, only 298 `.md`; the
# other 176 were 128 `.err`, 33 `.log`, 13 `.mp4`, 1 `.zip`, 1 `.json`. The
# first `.mp4` raised UnicodeDecodeError out of `_read_file_snippet` and
# aborted the whole review run.
# ---------------------------------------------------------------------------


def test_mixed_manifest_worklist_keeps_only_the_markdown_product() -> None:
    worklist, excluded = ac5._ac5_candidates(_MIXED_DIR)
    assert [i["file"] for i in worklist] == ["magazine-digest.md"]
    assert all(Path(i["path"]).suffix == ".md" for i in worklist)
    assert all(Path(i["path"]).exists() for i in worklist)


def test_mixed_manifest_excludes_every_non_reviewable_artifact_with_a_reason() -> None:
    _, excluded = ac5._ac5_candidates(_MIXED_DIR)
    by_suffix = {e["suffix"]: e["file"] for e in excluded}
    assert set(by_suffix) == {".log", ".err", ".mp4", ".zip", ".json"}
    assert all(e["reason"] for e in excluded), "an exclusion must always carry a reason"


def test_reviewable_suffix_rule_is_an_allowlist_of_text_products() -> None:
    """A format nobody anticipated must be excluded by default, not crash the run."""
    reviewable = [".md", ".markdown", ".html", ".htm", ".txt"]
    unreviewable = [
        ".mp4",
        ".zip",
        ".epub",
        ".mobi",
        ".mp3",
        ".pdf",
        ".sqlite",
        ".png",
        ".log",
        ".err",
        ".json",
        ".avif",
        ".docx",
    ]
    for suffix in reviewable:
        assert ac5.is_reviewable_product(Path(f"product{suffix}")), suffix
    for suffix in unreviewable:
        assert not ac5.is_reviewable_product(Path(f"product{suffix}")), suffix


def test_binary_artifact_in_a_mixed_manifest_does_not_abort_the_run() -> None:
    """The exact failure: a manifest mixing a product with a real .mp4/.zip."""
    report = ac5.run_ac5_review(_MIXED_DIR, semantic=False)
    assert report["summary"]["total"] == 1
    assert report["summary"]["excluded"] == 5
    assert report["summary"]["blocked"] == ""
    assert report["summary"]["passed"] == 0


def test_mixed_manifest_semantic_run_judges_only_the_text_product() -> None:
    with patch("autoinfo.llm.call_with_fallback", return_value=_Resp(_markdown_block("PASS"))) as m:
        with patch.object(ac5, "_channel_json_capable", return_value=False):
            report = ac5.run_ac5_review(_MIXED_DIR, semantic=True)
    assert m.call_count == 1, "a binary artifact must not consume a model call"
    assert [v["file"] for v in report["verdicts"]] == ["magazine-digest.md"]
    assert report["summary"]["risk"] == 1


def test_undecodable_markdown_file_escalates_instead_of_raising(tmp_path: Path) -> None:
    """A `.md` whose bytes are not UTF-8 must surface as ESCALATE, not crash."""
    bad = tmp_path / "corrupt-report.md"
    bad.write_bytes(b"# report\n" + b"\xe8\x00\xff" * 8)
    item = {"family": "corrupt-report", "file": bad.name, "path": str(bad)}

    with patch("autoinfo.llm.call_with_fallback") as mock_call:
        with patch.object(ac5, "_channel_json_capable", return_value=False):
            res = ac5.review_product(item, semantic=True)
    mock_call.assert_not_called()
    assert res["draft_verdict"] == "ESCALATE"
    assert res["llm_verdict"] == "ESCALATE"
    assert "unreadable" in res["note"].lower()


def test_oversized_product_escalates_instead_of_judging_a_fraction(tmp_path: Path) -> None:
    """A product past the reviewer's read window must ESCALATE, not be judged.

    Measured regression: at the former 8 000-char limit every ESCALATE row
    against ``outputs/`` was false — those files were 18 962-70 617 chars and
    complete, but the reviewer saw 8 012 and the model correctly reported that
    what it could see stopped mid-section.  A reviewer that cannot see the whole
    document has no basis to call the document truncated."""
    big = tmp_path / "huge-report.md"
    big.write_text("# report\n\n" + ("x" * 250_000), encoding="utf-8")
    item = {"family": "huge-report", "file": big.name, "path": str(big)}

    with patch("autoinfo.llm.call_with_fallback") as mock_call:
        with patch.object(ac5, "_channel_json_capable", return_value=False):
            res = ac5.review_product(item, semantic=True)
    mock_call.assert_not_called()
    assert res["draft_verdict"] == "ESCALATE"
    assert "cannot judge" in res["note"].lower()


def test_product_just_under_the_window_is_judged_on_all_of_it(tmp_path: Path) -> None:
    """The read window must be large enough that real products are read whole."""
    from battery import _FILE_SNIPPET_CHAR_LIMIT

    assert _FILE_SNIPPET_CHAR_LIMIT >= 140_000, (
        "the largest measured product is ~135 KB; a smaller window makes the "
        "reviewer judge a fraction of it"
    )
    body = "# report\n\n" + ("y" * 60_000)
    doc = tmp_path / "report.md"
    doc.write_text(body, encoding="utf-8")
    snippet = ac5._read_product_snippet(str(doc))
    assert snippet.truncated is False
    assert snippet.text == body


def test_read_product_snippet_never_propagates_unicode_decode_error() -> None:
    bad = Path(_MIXED_DIR / "02-PROCESSED" / "report-video-20260813-000000.mp4")
    snippet = ac5._read_product_snippet(str(bad))
    assert snippet.text == ""
    assert "decodable" in snippet.reason.lower()


def test_missing_manifest_file_is_a_recorded_skip_not_a_judged_placeholder(tmp_path: Path) -> None:
    item = {"family": "ghost", "file": "ghost.md", "path": str(tmp_path / "ghost.md")}
    with patch("autoinfo.llm.call_with_fallback") as mock_call:
        with patch.object(ac5, "_channel_json_capable", return_value=False):
            res = ac5.review_product(item, semantic=True)
    mock_call.assert_not_called()
    assert res["draft_verdict"] == "ESCALATE"
    assert "unreadable" in res["note"].lower()


def test_skip_is_visible_in_the_report_not_counted_as_reviewed(tmp_path: Path) -> None:
    bad = tmp_path / "corrupt-report.md"
    bad.write_bytes(b"\xe8\xff\xfe")
    (tmp_path / "report.md").write_text("# ok\n", encoding="utf-8")
    lines: list[str] = []
    with patch("autoinfo.llm.call_with_fallback", return_value=_Resp(_markdown_block("PASS"))):
        with patch.object(ac5, "_channel_json_capable", return_value=False):
            report = ac5.run_ac5_review(tmp_path, semantic=True, emit=lines.append)

    assert report["summary"]["passed"] == 0
    assert report["summary"]["escalate"] == 1
    assert report["summary"]["risk"] == 1
    reviewed = report["honesty"]["reviewed"]
    assert len(reviewed) == 2, "a skip is a reviewed attempt, not a dropped item"
    assert any("corrupt-report.md" in line for line in lines), lines


# ---------------------------------------------------------------------------
# Defect B — the fallback scan must be recursive
#
# Real product tree: outputs/ has 0 `.md` at the top level and 222 across 13
# per-domain subdirs, so `glob("*.md")` found nothing and the run reported
# "all clean" without reading a single product.
# ---------------------------------------------------------------------------


def test_fallback_scan_is_recursive_over_per_domain_subdirs(tmp_path: Path) -> None:
    (tmp_path / "medical-research").mkdir()
    (tmp_path / "general-news").mkdir()
    (tmp_path / "medical-research" / "report.md").write_text("# r\n", encoding="utf-8")
    (tmp_path / "medical-research" / "digest.md").write_text("# d\n", encoding="utf-8")
    (tmp_path / "general-news" / "magazine-digest.md").write_text("# m\n", encoding="utf-8")

    items = ac5.build_ac5_worklist(tmp_path)
    assert len(items) == 3
    assert {i["file"] for i in items} == {"report.md", "digest.md", "magazine-digest.md"}


def test_fallback_scan_is_sorted_deduplicated_and_deterministic(tmp_path: Path) -> None:
    for domain in ("zeta", "alpha", "mid"):
        (tmp_path / domain).mkdir()
        (tmp_path / domain / "report.md").write_text(f"# {domain}\n", encoding="utf-8")
    (tmp_path / "top.md").write_text("# top\n", encoding="utf-8")

    first = ac5.build_ac5_worklist(tmp_path)
    second = ac5.build_ac5_worklist(tmp_path)
    paths = [i["path"] for i in first]

    assert paths == sorted(paths), "the scan must be sorted, not filesystem order"
    assert len(set(paths)) == len(paths), "the scan must be de-duplicated"
    assert first == second, "the same tree must yield the same deterministic worklist"
    assert len(first) == 4


def test_fallback_scan_applies_the_same_suffix_rule(tmp_path: Path) -> None:
    (tmp_path / "medical-research").mkdir()
    (tmp_path / "medical-research" / "report.md").write_text("# r\n", encoding="utf-8")
    (tmp_path / "medical-research" / "report-video.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
    (tmp_path / "medical-research" / "bundle.zip").write_bytes(b"PK\x03\x04")
    (tmp_path / "medical-research" / "pipeline.log").write_text("INFO x\n", encoding="utf-8")

    items = ac5.build_ac5_worklist(tmp_path)
    assert [i["file"] for i in items] == ["report.md"]


def test_real_product_tree_shape_is_not_reported_as_clean(tmp_path: Path) -> None:
    """A delivery dir shaped like outputs/ (products only in subdirs) reviews them."""
    for domain in ("medical-research", "general-news", "retail"):
        (tmp_path / domain).mkdir()
        (tmp_path / domain / f"{domain}-report.md").write_text("# r\n", encoding="utf-8")

    report = ac5.run_ac5_review(tmp_path, semantic=False)
    assert report["summary"]["total"] == 3
    assert report["summary"]["blocked"] == ""


# ---------------------------------------------------------------------------
# Defect C — verdicts must stream, and an empty worklist must be LOUD
#
# Both real runs left a 278-byte log for 66 minutes, so "progressing" and
# "hung" were indistinguishable.
# ---------------------------------------------------------------------------


def test_emit_streams_header_then_one_line_per_form_then_summary() -> None:
    lines: list[str] = []
    ac5.run_ac5_review(_MIXED_DIR, semantic=False, emit=lines.append)

    assert lines[0].startswith("AC5 director-review DRAFT")
    assert lines[1] == "Worklist: 1 product form(s)"
    assert lines[-1].startswith("SUMMARY:")
    assert any(line.lstrip().startswith("[RISK] 1/1") for line in lines)
    assert len([line for line in lines if "[" in line and "/" in line]) == 1


def test_emit_reports_the_worklist_size_and_the_excluded_breakdown() -> None:
    lines: list[str] = []
    report = ac5.run_ac5_review(_MIXED_DIR, semantic=False, emit=lines.append)

    assert "Worklist: 1 product form(s)" in lines
    excluded_line = next(line for line in lines if line.startswith("EXCLUDED:"))
    assert "5 non-reviewable artifact" in excluded_line
    for suffix in (".err", ".log", ".mp4", ".zip", ".json"):
        assert suffix in excluded_line
    assert "never counted as reviewed" in excluded_line
    assert report["summary"]["excluded"] == 5


def test_emit_is_interleaved_with_judging_not_buffered_until_the_end(tmp_path: Path) -> None:
    """The first model call must already see prior verdict lines."""
    for index in range(3):
        (tmp_path / f"report-{index}.md").write_text(f"# {index}\n", encoding="utf-8")
    seen: list[int] = []
    lines: list[str] = []

    def _call(*args: Any, **kwargs: Any) -> Any:
        seen.append(len(lines))
        return _Resp(_markdown_block("PASS"))

    with patch("autoinfo.llm.call_with_fallback", side_effect=_call):
        with patch.object(ac5, "_channel_json_capable", return_value=False):
            ac5.run_ac5_review(tmp_path, semantic=True, emit=lines.append)

    assert seen == [2, 3, 4], f"verdicts were buffered, not streamed: {seen} / {len(lines)} lines"


def test_no_emit_means_no_narration() -> None:
    import io  # noqa: PLC0415
    from contextlib import redirect_stdout  # noqa: PLC0415

    buf = io.StringIO()
    with redirect_stdout(buf):
        report = ac5.run_ac5_review(_MIXED_DIR, semantic=False)
    assert buf.getvalue() == ""
    assert report["summary"]["total"] == 1


def test_empty_worklist_is_blocked_not_clean(tmp_path: Path) -> None:
    report = ac5.run_ac5_review(tmp_path, semantic=False)
    assert report["summary"]["total"] == 0
    assert report["summary"]["blocked"] == "no reviewable product form found"
    assert report["verdicts"] == []
    assert report["summary"]["passed"] == 0


def test_fully_excluded_worklist_is_blocked_not_clean(tmp_path: Path) -> None:
    """Every PROCESSED entry non-reviewable ⇒ 0 reviewable ⇒ loud, not clean."""
    manifest = {
        "files": [
            {
                "file": f"02-PROCESSED/artifact-{index}.mp4",
                "kind": "PROCESSED",
                "source": "s",
                "size": 10,
                "gates": {},
                "quality": "PASS",
            }
            for index in range(3)
        ],
        "rejected": [],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = ac5.run_ac5_review(tmp_path, semantic=False)
    assert report["summary"]["total"] == 0
    assert report["summary"]["excluded"] == 3
    assert report["summary"]["blocked"] != ""


def test_main_returns_two_on_empty_worklist_and_says_it_is_not_clean(
    tmp_path: Path, capsys: Any
) -> None:
    rc = ac5.main(["--delivery-dir", str(tmp_path), "--out", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 2
    assert "NOT a clean run" in captured.err
    assert "BLOCKED" in captured.out, "the blocked state must be on the narrated stream too"


def test_main_returns_two_when_every_manifest_entry_is_excluded(
    tmp_path: Path, capsys: Any
) -> None:
    (tmp_path / "bundle.zip").write_bytes(b"PK\x03\x04")
    manifest = {
        "files": [
            {
                "file": "02-PROCESSED/bundle.zip",
                "kind": "PROCESSED",
                "source": "s",
                "size": 4,
                "gates": {},
                "quality": "PASS",
            }
        ],
        "rejected": [],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    rc = ac5.main(["--delivery-dir", str(tmp_path), "--out", str(tmp_path)])
    assert rc == 2
    assert "NOT a clean run" in capsys.readouterr().err


def test_main_json_mode_keeps_stdout_parseable(tmp_path: Path, capsys: Any) -> None:
    rc = ac5.main(["--delivery-dir", str(_MIXED_DIR), "--out", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["summary"]["passed"] == 0
    assert "Worklist: 1 product form(s)" in captured.err


def test_blocked_run_still_persists_its_report(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    out = ac5._persist(ac5.run_ac5_review(empty, semantic=False), "v-test", tmp_path)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["report"]["summary"]["blocked"] != ""
    assert payload["report"]["summary"]["passed"] == 0
