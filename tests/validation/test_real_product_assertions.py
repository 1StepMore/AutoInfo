"""Real-product assertion scanner tests (issue #356).

Exercises ``scripts/real_product_assertions.py`` through its importable
``main(argv) -> int`` entry point (no subprocess), with ``tmp_path`` product
roots so the tests never touch the real ``outputs/`` tree:

1. a clean product → exit 0 and a correctly-shaped evidence JSON with
   ``failures == []``;
2. a product carrying a future year → exit 1 with the failure recorded under
   ``_no_year_hallucination``;
3. an unknown assertion name → exit 2 with the valid names listed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "real_product_assertions.py"

_SPEC = importlib.util.spec_from_file_location("real_product_assertions", SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
rpa = importlib.util.module_from_spec(_SPEC)
# Register before exec_module: the script defines a `@dataclass`, and
# dataclasses resolves the defining module through `sys.modules`.
sys.modules[_SPEC.name] = rpa
_SPEC.loader.exec_module(rpa)

_EVIDENCE_KEYS = {
    "schema_version",
    "tool",
    "generated_at",
    "commit",
    "issue",
    "roots",
    "assertions",
    "files_scanned",
    "totals",
    "failures",
}

_ASSERTION = "_no_year_hallucination"


def _write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_clean_product_exits_zero_with_evidence_shape(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "clean.md",
        "# Clean Product\n\n## Summary\n\nNo problems worth reporting here.\n",
    )
    json_out = tmp_path / "evidence.json"
    md_out = tmp_path / "evidence.md"

    code = rpa.main(
        [
            "--roots",
            str(tmp_path),
            "--assertions",
            _ASSERTION,
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ]
    )

    assert code == 0
    evidence: dict[str, Any] = json.loads(json_out.read_text(encoding="utf-8"))
    assert _EVIDENCE_KEYS <= set(evidence)
    assert evidence["failures"] == []
    assert evidence["files_scanned"] == 1
    assert evidence["assertions"] == [_ASSERTION]
    assert evidence["totals"]["total_failures"] == 0
    assert md_out.is_file()


def test_future_year_product_exits_one(tmp_path: Path) -> None:
    _write(tmp_path, "bad.md", "# Report\n\nIn 2031, adoption tripled.\n")
    json_out = tmp_path / "evidence.json"

    code = rpa.main(
        [
            "--roots",
            str(tmp_path),
            "--assertions",
            _ASSERTION,
            "--issue",
            "351",
            "--json-out",
            str(json_out),
        ]
    )

    assert code == 1
    evidence: dict[str, Any] = json.loads(json_out.read_text(encoding="utf-8"))
    assert evidence["files_scanned"] == 1
    assert len(evidence["failures"]) == 1
    failure = evidence["failures"][0]
    assert failure["assertion"] == _ASSERTION
    assert failure["severity"] == "P0"
    assert failure["path"].endswith("bad.md")
    assert evidence["issue"] == "351"
    assert evidence["totals"]["by_severity"]["P0"] == 1


def test_unknown_assertion_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "clean.md", "# Clean\n")

    code = rpa.main(
        [
            "--roots",
            str(tmp_path),
            "--assertions",
            "definitely_not_an_assertion",
        ]
    )

    assert code == 2
    err = capsys.readouterr().err
    assert "definitely_not_an_assertion" in err
    assert _ASSERTION in err
