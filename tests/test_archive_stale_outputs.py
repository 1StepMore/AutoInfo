"""Tests for scripts/archive_stale_outputs.py (#754).

The archiver isolates pre-assertion-era products by moving them out of
``outputs/``.  These tests lock the hard constraints: dry-run is inert,
move-only (never overwrite), date cutoff (inclusive), undated opt-in, and a
manifest rollback that restores identical bytes.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import archive_stale_outputs as arch  # noqa: E402  (sys.path insert above)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _run(capsys, argv: list[str]) -> tuple[int, str]:
    code = arch.main(argv)
    return code, capsys.readouterr().out


def _seed(root: Path) -> None:
    _write(root / "digest-20260815-120000.md", "august")
    _write(root / "digest-2026-09-30-120000.md", "september")
    _write(root / "digest-20261001-120000.md", "october")
    _write(root / "readme-without-date.md", "undated")


def test_dry_run_is_inert_and_counts_correctly(tmp_path: Path, capsys) -> None:
    root = tmp_path / "outputs"
    archive = tmp_path / "outputs-archive"
    _seed(root)
    before = _snapshot(root)

    code, out = _run(
        capsys,
        [
            "--roots",
            str(root),
            "--archive-dir",
            str(archive),
            "--dry-run",
            "--json",
        ],
    )

    assert code == 0
    assert _snapshot(root) == before
    assert not archive.exists()
    payload = json.loads(out)
    assert payload["total"] == 4
    assert payload["would_archive"] == 2
    assert payload["by_month"] == {"2026-08": 1, "2026-09": 1}
    assert payload["kept"] == 1
    assert payload["undated"] == 1


def test_apply_moves_only_on_or_before_cutoff(tmp_path: Path, capsys) -> None:
    root = tmp_path / "outputs"
    archive = tmp_path / "outputs-archive"
    _seed(root)

    code, _ = _run(
        capsys,
        ["--roots", str(root), "--archive-dir", str(archive), "--apply"],
    )

    assert code == 0
    assert not (root / "digest-20260815-120000.md").exists()
    assert not (root / "digest-2026-09-30-120000.md").exists()
    assert (root / "digest-20261001-120000.md").read_text(encoding="utf-8") == "october"
    assert (root / "readme-without-date.md").exists()
    assert (archive / "2026-08" / "digest-20260815-120000.md").read_text(encoding="utf-8") == "august"
    assert (
        archive / "2026-09" / "digest-2026-09-30-120000.md"
    ).read_text(encoding="utf-8") == "september"


def test_undated_is_left_alone_by_default(tmp_path: Path, capsys) -> None:
    root = tmp_path / "outputs"
    archive = tmp_path / "outputs-archive"
    _write(root / "matrix-report.md", "undated")

    code, out = _run(
        capsys,
        ["--roots", str(root), "--archive-dir", str(archive), "--apply", "--json"],
    )

    assert code == 0
    assert (root / "matrix-report.md").read_text(encoding="utf-8") == "undated"
    assert not list(archive.glob(f"{arch.UNDATED_BUCKET}/*"))
    payload = json.loads(out)
    assert payload["archived"] == 0
    assert payload["undated"] == 1


def test_include_undated_archives_them(tmp_path: Path, capsys) -> None:
    root = tmp_path / "outputs"
    archive = tmp_path / "outputs-archive"
    _write(root / "matrix-report.md", "undated")

    code, _ = _run(
        capsys,
        [
            "--roots",
            str(root),
            "--archive-dir",
            str(archive),
            "--apply",
            "--include-undated",
        ],
    )

    assert code == 0
    assert not (root / "matrix-report.md").exists()
    assert (
        archive / arch.UNDATED_BUCKET / "matrix-report.md"
    ).read_text(encoding="utf-8") == "undated"


def test_existing_destination_is_skipped_not_overwritten(tmp_path: Path, capsys) -> None:
    root = tmp_path / "outputs"
    archive = tmp_path / "outputs-archive"
    _write(root / "digest-20260815-120000.md", "incoming")
    _write(archive / "2026-08" / "digest-20260815-120000.md", "already-here")

    code, out = _run(
        capsys,
        ["--roots", str(root), "--archive-dir", str(archive), "--apply", "--json"],
    )

    assert code == 0
    assert (root / "digest-20260815-120000.md").read_text(encoding="utf-8") == "incoming"
    assert (
        archive / "2026-08" / "digest-20260815-120000.md"
    ).read_text(encoding="utf-8") == "already-here"
    payload = json.loads(out)
    assert payload["archived"] == 0
    assert payload["skipped_conflict"] == [str(root / "digest-20260815-120000.md")]


def test_rollback_restores_identical_bytes_and_layout(tmp_path: Path, capsys) -> None:
    root = tmp_path / "outputs"
    archive = tmp_path / "outputs-archive"
    _write(root / "nested" / "digest-20260815-120000.md", "august")
    _write(root / "digest-2026-09-01-120000.md", "september")
    before = _snapshot(root)

    code, _ = _run(
        capsys,
        ["--roots", str(root), "--archive-dir", str(archive), "--apply"],
    )
    assert code == 0
    manifest = next(archive.glob("manifest-*.json"))

    code, out = _run(capsys, ["--rollback", str(manifest), "--json"])

    assert code == 0
    assert _snapshot(root) == before
    payload = json.loads(out)
    assert payload["restored"] == 2
    assert not list(archive.glob("2026-*/*.md"))


def test_rollback_skips_when_source_already_exists(tmp_path: Path, capsys) -> None:
    root = tmp_path / "outputs"
    archive = tmp_path / "outputs-archive"
    _write(root / "digest-20260815-120000.md", "original")

    code, _ = _run(
        capsys,
        ["--roots", str(root), "--archive-dir", str(archive), "--apply"],
    )
    assert code == 0
    manifest = next(archive.glob("manifest-*.json"))
    _write(root / "digest-20260815-120000.md", "intruder")

    code, out = _run(capsys, ["--rollback", str(manifest), "--json"])

    assert code == 0
    assert (root / "digest-20260815-120000.md").read_text(encoding="utf-8") == "intruder"
    assert (
        archive / "2026-08" / "digest-20260815-120000.md"
    ).read_text(encoding="utf-8") == "original"
    payload = json.loads(out)
    assert payload["restored"] == 0
    assert payload["skipped"] == [str(root / "digest-20260815-120000.md")]


def test_multiple_roots_do_not_cross_contaminate(tmp_path: Path, capsys) -> None:
    root_a = tmp_path / "outputs-a"
    root_b = tmp_path / "outputs-b"
    archive = tmp_path / "outputs-archive"
    _write(root_a / "digest-20260815-120000.md", "a-old")
    _write(root_a / "digest-20261001-120000.md", "a-new")
    _write(root_b / "digest-20260915-120000.md", "b-old")
    _write(root_b / "digest-20261001-120000.md", "b-new")

    code, _ = _run(
        capsys,
        [
            "--roots",
            str(root_a),
            "--roots",
            str(root_b),
            "--archive-dir",
            str(archive),
            "--apply",
        ],
    )

    assert code == 0
    assert (archive / "2026-08" / "digest-20260815-120000.md").read_text(encoding="utf-8") == "a-old"
    assert (archive / "2026-09" / "digest-20260915-120000.md").read_text(encoding="utf-8") == "b-old"
    assert (root_a / "digest-20261001-120000.md").read_text(encoding="utf-8") == "a-new"
    assert (root_b / "digest-20261001-120000.md").read_text(encoding="utf-8") == "b-new"


def test_parse_date_prefers_last_match() -> None:
    assert arch.parse_date("digest-2026-09-01-20261002-120000.md").isoformat() == "2026-10-02"
    assert arch.parse_date("batch-20260901-20261003.md").isoformat() == "2026-10-03"
    assert arch.parse_date("no-date-here.md") is None
