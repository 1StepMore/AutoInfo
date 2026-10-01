"""Regression tests for the nightly workflow's pytest pipeline (#423).

The defect guarded here is pure CI shell semantics: a `run:` step pipes pytest
into `tee`, and GitHub Actions' default shell is `bash -e {0}` -- without
`pipefail` the pipeline's exit status is `tee`'s (always 0), so a red pytest
run is reported green and the `if: failure()` triage-artifact step can never
fire. The regression vehicle is therefore this pytest workflow-lint, NOT an
MCP validation scenario: there is no repo runtime behaviour to drive, only the
YAML text of the workflow files.

Two properties are pinned: the nightly step (which was missing the guard) and
every pytest-pipe across the workflow set (so a future edit cannot drop it).

NOTE: the workflows use the YAML 1.1 `on:` key, which PyYAML's safe_load
misparses as the boolean `True`. We parse with `yaml.BaseLoader` (a
YAML-1.1-safe approach) so the document loads with the real `on` key.
"""

from pathlib import Path
from typing import Any, cast

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
NIGHTLY = WORKFLOWS / "nightly.yml"
CI = WORKFLOWS / "ci.yml"
COVERAGE = WORKFLOWS / "coverage.yml"


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.load(path.read_text(), Loader=yaml.BaseLoader))


def _run_blocks(path: Path) -> list[str]:
    """Every `run:` script in every job of a workflow, in document order."""
    data = _load(path)
    blocks: list[str] = []
    for job in data["jobs"].values():
        for step in cast(list[dict[str, Any]], job.get("steps", [])):
            run = step.get("run")
            if run is not None:
                blocks.append(str(run))
    return blocks


def _pytest_pipe_blocks(path: Path) -> list[str]:
    return [b for b in _run_blocks(path) if "pytest" in b and "|" in b]


def test_nightly_pytest_pipe_has_pipefail() -> None:
    """The nightly pytest|tee pipeline must fail the step when pytest fails.

    Without `set -o pipefail` the step inherits `tee`'s success, the failure is
    swallowed as a false green, and the downstream `if: failure()` triage
    artifact never uploads. The guard must precede the pytest invocation.
    """
    blocks = _pytest_pipe_blocks(NIGHTLY)
    assert blocks, "nightly has no pytest pipeline step to guard"
    for block in blocks:
        lines = block.splitlines()
        guard_at = next(
            (
                i
                for i, ln in enumerate(lines)
                if "set -o pipefail" in ln or "set -euo pipefail" in ln
            ),
            None,
        )
        pytest_at = next(i for i, ln in enumerate(lines) if "pytest" in ln)
        assert guard_at is not None, f"pipefail missing from nightly run block:\n{block}"
        assert guard_at < pytest_at, f"pipefail must precede pytest:\n{block}"


def test_all_pytest_pipes_across_workflows_have_pipefail() -> None:
    """Every workflow pytest pipe carries the guard (pins the known-good sites).

    `ci.yml` and `coverage.yml` are already correct; this test exists so a
    future edit cannot silently drop the guard from any of the three.
    """
    for path in (NIGHTLY, CI, COVERAGE):
        blocks = _pytest_pipe_blocks(path)
        assert blocks, f"{path.name} has no pytest pipeline step"
        for block in blocks:
            assert "pipefail" in block, f"pipefail missing from {path.name} run block:\n{block}"
