"""Regression tests for scripts/nightly_ledger.py (#566).

The live zone of NIGHTLY.md is generated from the append-only ledger. The
marker pairs are human-readable anchors only: ``--check`` must gate the whole
live segment (from the first ``## 【活区】`` heading to EOF), otherwise a
hand-edit between sections slips through CI and survives ``--write``.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

# scripts/ is not a package — load it via sys.path like the script itself does.
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import nightly_ledger as nl  # noqa: E402  (sys.path insert above)

NIGHTLY = Path(__file__).resolve().parent.parent / "docs" / "dev" / "plans" / "NIGHTLY.md"
LEDGER = Path(__file__).resolve().parent.parent / "docs" / "dev" / "plans" / "nightly-ledger.jsonl"


def _stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    nightly = tmp_path / "NIGHTLY.md"
    ledger = tmp_path / "nightly-ledger.jsonl"
    nightly.write_text(NIGHTLY.read_text(encoding="utf-8"), encoding="utf-8")
    ledger.write_text(LEDGER.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(nl, "NIGHTLY_PATH", nightly)
    monkeypatch.setattr(nl, "LEDGER_PATH", ledger)
    return nightly


def _insert_after_heading(text: str) -> str:
    heading = "## 【活区】下一步队列\n"
    return text.replace(heading, heading + "OUTSIDE-EDIT\n", 1)


def _edit_inside_marker(text: str) -> str:
    return text.replace("先纵后横", "先纵后横改", 1)


def _delete_marker(text: str) -> str:
    marker = "<!-- LEDGER:BEGIN gap_snapshot -->\n"
    assert marker in text
    return text.replace(marker, "", 1)


def _rename_heading(text: str) -> str:
    return text.replace("## 【活区】摩擦账本", "## 【活区】摩擦账本X", 1)


@pytest.mark.parametrize(
    "mutate",
    [
        _insert_after_heading,
        _edit_inside_marker,
        _delete_marker,
        _rename_heading,
    ],
    ids=["outside-marker", "inside-marker", "missing-marker", "heading"],
)
def test_hand_edit_outside_markers_fails_check_and_write_heals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
    capsys: pytest.CaptureFixture[str],
) -> None:
    nightly = _stage(tmp_path, monkeypatch)
    original = nightly.read_text(encoding="utf-8")
    frozen = original[: original.index(nl.LIVE_ZONE_HEADING)]
    frozen_sha = hashlib.sha256(frozen.encode()).hexdigest()

    mutated = mutate(original)
    assert mutated != original
    nightly.write_text(mutated, encoding="utf-8")

    assert nl.main(["--check"]) == 1
    assert "DRIFT: live zone does not match the ledger" in capsys.readouterr().err

    assert nl.main(["--write"]) == 0
    assert nl.main(["--check"]) == 0
    healed = nightly.read_text(encoding="utf-8")
    assert healed == original
    assert hashlib.sha256(healed[: len(frozen)].encode()).hexdigest() == frozen_sha


def test_clean_nightly_file_passes_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stage(tmp_path, monkeypatch)
    assert nl.main(["--check"]) == 0


def test_live_zone_heading_missing_fails_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nightly = _stage(tmp_path, monkeypatch)
    text = nightly.read_text(encoding="utf-8")
    nightly.write_text(text.replace(nl.LIVE_ZONE_HEADING, "## 【活区】改名了", 1), encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        nl.main(["--check"])
    assert excinfo.value.code not in (0, None)
