# mypy: ignore-errors
"""Guard the real ``outputs/`` tree against persisted test fixtures.

Test fixtures had been written into the repository's real ``outputs/``
directory and then counted as produced products by the coverage scanner.
This module fails when a fixture sentinel reappears, or when a persisted
artifact is too small to be a real product.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
SCRIPT = ROOT / "scripts" / "coverage_matrix.py"

_SPEC_IMPORT = importlib.util.spec_from_file_location("coverage_matrix", SCRIPT)
assert _SPEC_IMPORT is not None and _SPEC_IMPORT.loader is not None
cm = importlib.util.module_from_spec(_SPEC_IMPORT)
_SPEC_IMPORT.loader.exec_module(cm)

MAX_REAL_ARTIFACT_BYTES = 200
FIXTURE_SENTINELS = (
    b"ID3FAKEMP3",
    b"fake-video-bytes",
    b"real-mp4-bytes",
    b"# Cross Domain\n\nbody",
    b"Some **content** here",
    b"Real content.",
)


def scan_fixture_artifacts(outputs_root: Path) -> list[str]:
    hits: list[str] = []
    if not outputs_root.is_dir():
        return hits
    for path in sorted(outputs_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for sentinel in FIXTURE_SENTINELS:
            if sentinel in data:
                hits.append(f"{path}: fixture sentinel {sentinel!r}")
        if len(data) < MAX_REAL_ARTIFACT_BYTES and cm._PERSISTED_RE.match(path.name):
            hits.append(
                f"{path}: persisted artifact is {len(data)} bytes "
                f"(< {MAX_REAL_ARTIFACT_BYTES}) — not a real product"
            )
    return hits


def test_outputs_tree_has_no_fixture_artifacts() -> None:
    assert scan_fixture_artifacts(OUTPUTS) == []


def test_guard_detects_reintroduced_sentinel(tmp_path: Path) -> None:
    fixture = tmp_path / "outputs" / "medical-research" / "column-video-20261025-133622.mp4"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b"fake-video-bytes")

    hits = scan_fixture_artifacts(tmp_path / "outputs")

    assert hits and "column-video-20261025-133622.mp4" in hits[0]


def test_guard_detects_undersized_persisted_artifact(tmp_path: Path) -> None:
    fixture = tmp_path / "outputs" / "medical-research" / "digest-markdown-20261025-133621.md"
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b"x")

    hits = scan_fixture_artifacts(tmp_path / "outputs")

    assert hits and "digest-markdown-20261025-133621.md" in hits[0]
