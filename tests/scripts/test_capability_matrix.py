"""Tests for the 27xN capability matrix driver (scripts/capability_matrix.py).

Hermetic: no network, no real product generation.  The only filesystem writes
are under ``tmp_path``; the L2 checker is monkeypatched so the tests do not
depend on heavy artifacts or on ``format_structure.py`` internals.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

# scripts/ is not a package — load it via sys.path like the script itself does.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import capability_matrix as cm  # noqa: E402  (sys.path insert above)

_REAL_SPEC = Path(__file__).resolve().parents[2] / "docs" / "dev" / "specs" / "end-user-matrix.yaml"


# ---------------------------------------------------------------------------
# 1. --list parity against the real spec
# ---------------------------------------------------------------------------


def test_list_parity_from_real_spec() -> None:
    combinations = cm.derive_combinations(_REAL_SPEC)
    assert len(combinations) == 27
    assert sum(1 for c in combinations if c.gated) == 12
    assert sum(1 for c in combinations if not c.gated) == 15


def test_list_cli_prints_27_pairs(capsys: Any) -> None:
    rc = cm.main(["--list", "--spec", str(_REAL_SPEC)])
    assert rc == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 27
    assert sum(1 for line in lines if line.endswith("\tgated")) == 12
    assert sum(1 for line in lines if line.endswith("\tnon-gated")) == 15
    assert "digest:video" not in {line.split("\t")[0] for line in lines}
    assert "report:video" in {line.split("\t")[0] for line in lines}


# ---------------------------------------------------------------------------
# 2. tmp-spec derivation proves the list is not hardcoded
# ---------------------------------------------------------------------------


def test_tmp_spec_adds_a_28th_combination(tmp_path: Path) -> None:
    data = yaml.safe_load(_REAL_SPEC.read_text(encoding="utf-8"))
    flipped = False
    for cell in data["required_cells"]:
        if cell.get("product") == "digest" and cell.get("format") == "video":
            cell["capability"] = "implemented"
            flipped = True
            break
    assert flipped, "spec no longer carries a digest:video cell to flip"
    tmp_spec = tmp_path / "end-user-matrix.yaml"
    tmp_spec.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    combinations = cm.derive_combinations(tmp_spec)
    assert len(combinations) == 28
    assert any(c.product == "digest" and c.format == "video" for c in combinations)


# ---------------------------------------------------------------------------
# 3. routing table contract
# ---------------------------------------------------------------------------


def test_every_route_calls_the_real_generator_with_right_kwargs() -> None:
    combinations, _gated, spec_products = cm.load_spec(_REAL_SPEC)
    cm.validate_routes(combinations, spec_products)
    assert {c.product for c in combinations} <= set(cm.ROUTES)

    template = object()
    templated = {"premium-briefing", "column", "magazine-digest", "enterprise-briefing"}
    for product, route in cm.ROUTES.items():
        ctx = cm.RouteContext(
            domain="medical-research",
            format="markdown",
            product=product,
            topic="IVF",
            template=template,
        )
        call = route(ctx)
        assert "product" not in call.kwargs, f"{product} must not pass a `product=` kwarg"
        assert call.kwargs["domain"] == "medical-research"
        assert call.kwargs["format"] == "markdown"
        if product in templated:
            assert route.needs_template is True
            assert call.kwargs["product_template"] is template
        else:
            assert route.needs_template is False
            assert "product_template" not in call.kwargs
        if product == "presentation":
            assert call.kwargs["topic"] == "IVF"
        if product == "tutorial":
            assert "topic" not in call.kwargs


# ---------------------------------------------------------------------------
# 4. monotone-layer invariant
# ---------------------------------------------------------------------------


def test_l3_is_impossible_when_l2_fails() -> None:
    verdict = cm.compute_layers(l1_pass=True, l2_passed=False, artifact_bytes=10_000)
    assert verdict.l1 is True
    assert verdict.l2 is False
    assert verdict.l3 is False
    assert verdict.reached == "L1"


def test_l2_is_impossible_when_l1_fails() -> None:
    verdict = cm.compute_layers(l1_pass=False, l2_passed=True, artifact_bytes=10_000)
    assert verdict.l1 is False
    assert verdict.l2 is False
    assert verdict.l3 is False
    assert verdict.reached == "blocked-empty-artifact"


# ---------------------------------------------------------------------------
# 5. checkpoint/resume + --only-assert degradation
# ---------------------------------------------------------------------------


def _seed_matrix(out_dir: Path, artifact: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = out_dir / "matrix.json"
    row = {
        "domain": "medical-research",
        "product": "digest",
        "format": "markdown",
        "gated": False,
        "keyed": "unkeyed",
        "artifact": str(artifact),
        "reached": "L3",
        "l1": True,
        "l2": True,
        "l3": True,
        "detail": "seeded",
        "duration_s": 1.0,
    }
    checkpoint.write_text(
        json.dumps({"generated_at": "seed", "domains": ["medical-research"], "rows": [row]}),
        encoding="utf-8",
    )
    return checkpoint


def test_resume_skips_recorded_cell_then_assert_degrades(
    tmp_path: Path, monkeypatch: Any
) -> None:
    out_dir = tmp_path / "out"
    artifact = tmp_path / "digest-markdown.md"
    artifact.write_text("# Digest\n\n" + "word " * 300, encoding="utf-8")
    checkpoint = _seed_matrix(out_dir, artifact)

    monkeypatch.setattr(cm, "check_l2", lambda path: {"passed": True, "checks": {}})

    def _must_not_generate(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("recorded cell must be skipped on resume")

    monkeypatch.setattr(cm, "generate_cell", _must_not_generate)

    rc = cm.main(
        [
            "--out",
            str(out_dir),
            "--domains",
            "medical-research",
            "--only",
            "digest:markdown",
        ]
    )
    assert rc == 0

    artifact.unlink()
    rc = cm.main(
        [
            "--out",
            str(out_dir),
            "--domains",
            "medical-research",
            "--only",
            "digest:markdown",
            "--only-assert",
        ]
    )
    assert rc == 1

    rows = json.loads(checkpoint.read_text(encoding="utf-8"))["rows"]
    assert len(rows) == 1
    assert rows[0]["reached"] == "blocked-empty-artifact"
    assert rows[0]["l1"] is False
    assert rows[0]["l2"] is False
    assert rows[0]["l3"] is False


# ---------------------------------------------------------------------------
# 6. --only-assert without a recorded row
# ---------------------------------------------------------------------------


def test_only_assert_without_recorded_row_exits_1(tmp_path: Path, capsys: Any) -> None:
    out_dir = tmp_path / "out"
    rc = cm.main(
        [
            "--out",
            str(out_dir),
            "--domains",
            "medical-research",
            "--only",
            "digest:markdown",
            "--only-assert",
        ]
    )
    assert rc == 1
    assert "no recorded row" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 7. T17: no-key runs skip LLM-gated cells and collapse non-gated retry budget
# ---------------------------------------------------------------------------


def _capture_route(seen: list[Any], *, fail: bool = True) -> Any:
    def factory(ctx: Any) -> Any:
        seen.append(ctx)
        if fail:
            def _boom(**kwargs: Any) -> Any:
                raise RuntimeError("generation stopped by test")

            return cm.GenerationCall(_boom, {}, False)
        return cm.GenerationCall(lambda **kwargs: "", {}, False)

    return cm.Route(factory, needs_template=False)


def test_no_key_gated_cell_is_blocked_without_invoking_route(
    tmp_path: Path, monkeypatch: Any
) -> None:
    calls: list[Any] = []
    monkeypatch.setitem(cm.ROUTES, "premium-briefing", _capture_route(calls))
    combo = cm.Combination(product="premium-briefing", format="markdown", gated=True)

    row = cm.generate_cell(
        combo,
        domain="medical-research",
        topic="IVF",
        artifact_root=tmp_path,
        force=False,
        keyed="unkeyed",
        llm_available=False,
    )

    assert row["reached"] == "blocked-no-llm-key"
    assert "LLM prerequisite is provably absent" in row["detail"]
    assert calls == []


def test_no_key_non_gated_cell_collapses_retry_budget(
    tmp_path: Path, monkeypatch: Any
) -> None:
    seen: list[Any] = []
    monkeypatch.setitem(cm.ROUTES, "digest", _capture_route(seen))
    combo = cm.Combination(product="digest", format="markdown", gated=False)

    cm.generate_cell(
        combo,
        domain="medical-research",
        topic="IVF",
        artifact_root=tmp_path,
        force=False,
        keyed="unkeyed",
        llm_available=False,
    )

    assert seen[0].disable_llm is True
    assert seen[0].max_synthesis_attempts == 1
    assert seen[0].retry_backoff_seconds == 0.0


def test_explicit_llm_flags_override_no_key_defaults(
    tmp_path: Path, monkeypatch: Any
) -> None:
    seen: list[Any] = []
    monkeypatch.setitem(cm.ROUTES, "report", _capture_route(seen))
    combo = cm.Combination(product="report", format="markdown", gated=False)

    cm.generate_cell(
        combo,
        domain="medical-research",
        topic="IVF",
        artifact_root=tmp_path,
        force=False,
        keyed="unkeyed",
        llm_available=False,
        llm_attempts=5,
        llm_backoff=2.0,
    )

    assert seen[0].disable_llm is True
    assert seen[0].max_synthesis_attempts == 5
    assert seen[0].retry_backoff_seconds == 2.0
