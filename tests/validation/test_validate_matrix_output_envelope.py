"""CLI-surface tests for ``autoinfo validate`` output paths.

Complements ``test_validate_matrix_cli.py`` / ``test_validate_matrix_stability.py``
by covering the surface those files leave untested:

* the ``_default_domains`` config-resolution paths,
* ``matrix --html-out`` (the human HTML branch),
* the global ``--json`` envelope (T-S-07) for ``matrix`` / ``diff`` /
  ``stability`` — success AND failure exits,
* the ``PRODUCT_STATUS`` pseudo-assertion table rows (missing/error products),
* the #340 reconciliation hard-exit inside ``stability``.

All runs are deterministic: ``run_matrix`` / ``save_report_card`` are patched
where a real LLM generation would otherwise occur, and batch trees are built
under ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from autoinfo import validation_matrix as vm
from autoinfo.cli import validate as _v
from autoinfo.cli._output import set_global_json
from autoinfo.cli.validate import app

runner = CliRunner()

CLEAN = """# AI Commercial Report

**Domain**: ai-commercial
**Sections**: 2

## Summary

AI funding accelerated this week.

## Key Takeaways

### 1. Startup A raised $50M (Source: https://techcrunch.com/1)
Monitor developments.

### 2. Startup B raised $30M (Source: https://techcrunch.com/2)
Watch consolidation.

## References

1. **Startup A** — https://techcrunch.com/1 (techcrunch)
2. **Startup B** — https://techcrunch.com/2 (techcrunch)
"""

PLACEHOLDER = "# T\n\n_No articles found for general-news in the Weekly period._\n"


@pytest.fixture()
def global_json_mode() -> Any:
    """Activate the canonical global ``--json`` envelope for one test."""
    set_global_json(True)
    try:
        yield
    finally:
        set_global_json(False)


def _matrix_report(*, failures: int = 0, batch_id: str = "b1") -> vm.MatrixReport:
    report = vm.MatrixReport(
        generated_at="2026-08-21T00:00:00Z",
        commit="c",
        batch_id=batch_id,
    )
    report.products = [
        {
            "domain": "d",
            "product": "digest",
            "status": "ok" if not failures else "missing",
            "assertions": [],
        }
    ]
    report.summary = {
        "domains": ["d"],
        "products": ["digest"],
        "total_products": 1,
        "total_asserts": 0,
        "failures": failures,
        "failing_assertions": 0,
        "missing_products": failures,
        "error_products": 0,
    }
    return report


def _write_card(
    path: Path,
    *,
    batch_id: str,
    domain: str,
    product: str,
    status: str,
    assertion_passed: bool,
) -> Path:
    card = {
        "schema_version": 2,
        "tool": "autoinfo validate --matrix",
        "batch_id": batch_id,
        "products": [
            {
                "domain": domain,
                "product": product,
                "status": status,
                "assertions": [{"assertion": "_not_empty", "passed": assertion_passed}],
            }
        ],
    }
    path.write_text(json.dumps(card), encoding="utf-8")
    return path


def _write_batch(root: Path, batch_id: str, body: str) -> None:
    out = root / batch_id / "products" / "ai-commercial" / f"report-markdown-{batch_id}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")


class _Domain:
    def __init__(self, name: str, active: bool = True) -> None:
        self.name = name
        self.active = active


class _Config:
    def __init__(self, domains: list[_Domain]) -> None:
        self.domains = domains


# ======================================================================
# _default_domains config resolution
# ======================================================================


class TestDefaultDomains:
    def test_reads_active_domains_from_config(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text("domains: []\n", encoding="utf-8")
        with (
            patch("autoinfo.config.get_config_path", return_value=str(cfg)),
            patch(
                "autoinfo.config.load_config",
                return_value=_Config([_Domain("d1"), _Domain("d2", active=False)]),
            ),
        ):
            assert _v._default_domains() == ["d1"]

    def test_no_active_domains_falls_back(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text("domains: []\n", encoding="utf-8")
        with (
            patch("autoinfo.config.get_config_path", return_value=str(cfg)),
            patch("autoinfo.config.load_config", return_value=_Config([])),
        ):
            assert _v._default_domains() == [
                "medical-research",
                "ai-commercial",
                "financial-intelligence",
            ]

    def test_config_load_error_falls_back(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.yaml"
        cfg.write_text("bad: [\n", encoding="utf-8")
        with (
            patch("autoinfo.config.get_config_path", return_value=str(cfg)),
            patch("autoinfo.config.load_config", side_effect=RuntimeError("boom")),
        ):
            assert _v._default_domains() == [
                "medical-research",
                "ai-commercial",
                "financial-intelligence",
            ]


# ======================================================================
# matrix --html-out
# ======================================================================


class TestMatrixHtmlOut:
    def test_writes_html_report_and_announces(self, tmp_path: Path) -> None:
        html = tmp_path / "card.html"
        with (
            patch("autoinfo.cli.validate.run_matrix", return_value=_matrix_report()),
            patch(
                "autoinfo.cli.validate.save_report_card",
                return_value=tmp_path / "snap" / "report-card.json",
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "matrix",
                    "--batch",
                    "b1",
                    "--domains",
                    "d",
                    "--products",
                    "digest",
                    "--html-out",
                    str(html),
                ],
            )
        assert result.exit_code == 0, result.output
        assert html.is_file()
        assert "report card" in html.read_text(encoding="utf-8")
        assert "report card HTML" in result.output


# ======================================================================
# matrix global --json envelope
# ======================================================================


class TestMatrixGlobalJson:
    def test_success_envelope_and_suppressed_human_output(
        self,
        tmp_path: Path,
        global_json_mode: None,
    ) -> None:
        with (
            patch("autoinfo.cli.validate.run_matrix", return_value=_matrix_report()),
            patch(
                "autoinfo.cli.validate.save_report_card",
                return_value=tmp_path / "snap" / "card.json",
            ),
        ):
            result = runner.invoke(
                app,
                ["matrix", "--batch", "b1", "--domains", "d", "--products", "digest"],
            )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["batch_id"] == "b1"
        assert payload["data"]["report_card"]["summary"]["failures"] == 0
        # Human report-card render is suppressed in JSON mode.
        assert "Report card" not in result.output

    def test_failure_envelope_exits_one(
        self,
        tmp_path: Path,
        global_json_mode: None,
    ) -> None:
        with (
            patch("autoinfo.cli.validate.run_matrix", return_value=_matrix_report(failures=1)),
            patch(
                "autoinfo.cli.validate.save_report_card",
                return_value=tmp_path / "snap" / "card.json",
            ),
        ):
            result = runner.invoke(
                app,
                ["matrix", "--batch", "b1", "--domains", "d", "--products", "digest"],
            )
        assert result.exit_code == 1, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["report_card"]["summary"]["failures"] == 1


# ======================================================================
# diff global --json envelope + PRODUCT_STATUS table
# ======================================================================


class TestDiffGlobalJson:
    def test_clean_diff_envelope_exits_zero(
        self,
        tmp_path: Path,
        global_json_mode: None,
    ) -> None:
        prev = _write_card(
            tmp_path / "prev.json",
            batch_id="p",
            domain="d",
            product="report",
            status="ok",
            assertion_passed=True,
        )
        cur = _write_card(
            tmp_path / "cur.json",
            batch_id="c",
            domain="d",
            product="report",
            status="ok",
            assertion_passed=True,
        )
        result = runner.invoke(app, ["diff", str(prev), str(cur)])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["diff"]["regressed"] == []
        assert payload["data"]["diff"]["new"] == []

    def test_regression_envelope_exits_one(
        self,
        tmp_path: Path,
        global_json_mode: None,
    ) -> None:
        prev = _write_card(
            tmp_path / "prev.json",
            batch_id="p",
            domain="d",
            product="report",
            status="ok",
            assertion_passed=True,
        )
        cur = _write_card(
            tmp_path / "cur.json",
            batch_id="c",
            domain="d",
            product="report",
            status="ok",
            assertion_passed=False,
        )
        result = runner.invoke(app, ["diff", str(prev), str(cur)])
        assert result.exit_code == 1, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["diff"]["regressed"] == [["d", "report", "_not_empty"]]

    def test_product_status_row_renders_missing_status(self, tmp_path: Path) -> None:
        """A missing product is a ``PRODUCT_STATUS`` diff item; the human table
        must substitute the real status word, not print ``@status``."""
        prev = _write_card(
            tmp_path / "prev.json",
            batch_id="p",
            domain="d",
            product="report",
            status="ok",
            assertion_passed=True,
        )
        cur = _write_card(
            tmp_path / "cur.json",
            batch_id="c",
            domain="d",
            product="report",
            status="missing",
            assertion_passed=True,
        )
        result = runner.invoke(app, ["diff", str(prev), str(cur)])
        assert result.exit_code == 1, result.output
        assert "product missing" in result.output
        assert vm.PRODUCT_STATUS not in result.output


# ======================================================================
# stability global --json envelope + PRODUCT_STATUS table + #340 hard exit
# ======================================================================


class TestStabilityGlobalJson:
    def test_stable_envelope_exits_zero(
        self,
        tmp_path: Path,
        global_json_mode: None,
    ) -> None:
        _write_batch(tmp_path, "a", CLEAN)
        _write_batch(tmp_path, "b", CLEAN)
        with patch("autoinfo.validation_matrix._current_commit", return_value="abc"):
            result = runner.invoke(
                app,
                [
                    "stability",
                    "a",
                    "b",
                    "--snapshot-dir",
                    str(tmp_path),
                    "--domains",
                    "ai-commercial",
                    "--products",
                    "report",
                ],
            )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["stable"] is True

    def test_unstable_envelope_exits_one(
        self,
        tmp_path: Path,
        global_json_mode: None,
    ) -> None:
        _write_batch(tmp_path, "a", CLEAN)
        _write_batch(tmp_path, "b", PLACEHOLDER)
        with patch("autoinfo.validation_matrix._current_commit", return_value="abc"):
            result = runner.invoke(
                app,
                [
                    "stability",
                    "a",
                    "b",
                    "--snapshot-dir",
                    str(tmp_path),
                    "--domains",
                    "ai-commercial",
                    "--products",
                    "report",
                ],
            )
        assert result.exit_code == 1, result.output
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["data"]["stable"] is False
        assert payload["data"]["counts"]["regressed"] >= 1


class TestStabilityNonGlobal:
    def test_reconciliation_failure_is_hard_exit(self, tmp_path: Path) -> None:
        """#340 — a bucket/failure mismatch is a hard non-zero exit even on the
        human path (not just the JSON envelope)."""
        _write_batch(tmp_path, "a", CLEAN)
        _write_batch(tmp_path, "b", CLEAN)
        with (
            patch("autoinfo.validation_matrix._current_commit", return_value="abc"),
            patch(
                "autoinfo.cli.validate.card_issue_counts",
                side_effect=[
                    {"failing_assertions": 0, "missing_products": 0, "error_products": 0},
                    {"failing_assertions": 99, "missing_products": 0, "error_products": 0},
                ],
            ),
        ):
            result = runner.invoke(
                app,
                [
                    "stability",
                    "a",
                    "b",
                    "--snapshot-dir",
                    str(tmp_path),
                    "--domains",
                    "ai-commercial",
                    "--products",
                    "report",
                ],
            )
        assert result.exit_code == 1, result.output
        assert "do not reconcile" in result.output

    def test_product_status_row_renders_missing_status(self, tmp_path: Path) -> None:
        """Only batch a exists → batch b's product row is ``missing`` and the
        stability table must substitute the real status for ``@status``."""
        _write_batch(tmp_path, "a", CLEAN)
        with patch("autoinfo.validation_matrix._current_commit", return_value="abc"):
            result = runner.invoke(
                app,
                [
                    "stability",
                    "a",
                    "b",
                    "--snapshot-dir",
                    str(tmp_path),
                    "--domains",
                    "ai-commercial",
                    "--products",
                    "report",
                ],
            )
        assert result.exit_code == 1, result.output
        assert "product missing" in result.output
        assert vm.PRODUCT_STATUS not in result.output
