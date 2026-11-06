"""Doctor diagnostics tests (T05): read-only, hint-carrying, no P0 class missing."""

from __future__ import annotations

from pathlib import Path

from autoinfo.gov import doctor as doctor_mod


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_doctor_report_shape() -> None:
    data = doctor_mod.doctor(_repo_root())
    assert data["platform"] in {"Windows", "Linux", "Darwin"}
    ids = {c["id"] for c in data["checks"]}
    assert {
        "make",
        "interpreters",
        "core.autocrlf",
        "tracked-crlf",
        "core.longpaths",
        "venv",
        "core.filemode",
        "core.symlinks",
    } <= ids
    assert data["p0"] == sum(1 for c in data["checks"] if c["severity"] == "P0")
    for check in data["checks"]:
        if check["severity"] in {"P0", "P1", "P2"}:
            assert check["hint"], f"{check['id']} needs a hint"
        assert check["state"]


def test_doctor_is_read_only(tmp_path: Path) -> None:
    """Running doctor must not mutate the repo (or the tmp stand-in)."""
    marker = tmp_path / "marker.txt"
    marker.write_text("untouched", encoding="utf-8")
    doctor_mod.doctor(tmp_path)
    assert marker.read_text(encoding="utf-8") == "untouched"
    assert not (tmp_path / ".git" / "config.bak").exists()
